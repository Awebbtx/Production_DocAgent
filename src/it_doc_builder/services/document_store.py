from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from it_doc_builder.config import Settings

DEFAULT_RETENTION_DAYS = 2  # 48 hours
DEFAULT_MAX_TOTAL_BYTES = 5 * 1024 ** 3  # 5 GB


class DocumentStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._settings.auth_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id          TEXT PRIMARY KEY,
                    username        TEXT NOT NULL,
                    title           TEXT NOT NULL,
                    document_type   TEXT NOT NULL,
                    tracking_code   TEXT NOT NULL,
                    revision        TEXT NOT NULL DEFAULT 'R01',
                    document_status TEXT NOT NULL DEFAULT 'Draft',
                    classification  TEXT NOT NULL DEFAULT 'Internal',
                    retention_policy TEXT NOT NULL DEFAULT '',
                    document_owner  TEXT NOT NULL DEFAULT '',
                    approver        TEXT NOT NULL DEFAULT '',
                    html_path       TEXT,
                    docx_path       TEXT,
                    file_size_bytes INTEGER NOT NULL DEFAULT 0,
                    created_at      TEXT NOT NULL
                )
                """
            )
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(documents)").fetchall()
            }
            if "revision" not in cols:
                conn.execute("ALTER TABLE documents ADD COLUMN revision TEXT NOT NULL DEFAULT 'R01'")
            if "document_status" not in cols:
                conn.execute("ALTER TABLE documents ADD COLUMN document_status TEXT NOT NULL DEFAULT 'Draft'")
            if "classification" not in cols:
                conn.execute("ALTER TABLE documents ADD COLUMN classification TEXT NOT NULL DEFAULT 'Internal'")
            if "retention_policy" not in cols:
                conn.execute("ALTER TABLE documents ADD COLUMN retention_policy TEXT NOT NULL DEFAULT ''")
            if "document_owner" not in cols:
                conn.execute("ALTER TABLE documents ADD COLUMN document_owner TEXT NOT NULL DEFAULT ''")
            if "approver" not in cols:
                conn.execute("ALTER TABLE documents ADD COLUMN approver TEXT NOT NULL DEFAULT ''")
            conn.commit()

    def save_document(
        self,
        *,
        doc_id: str,
        username: str,
        title: str,
        document_type: str,
        tracking_code: str,
        revision: str,
        document_status: str,
        classification: str,
        retention_policy: str,
        document_owner: str,
        approver: str,
        html_path: Path | None,
        docx_path: Path | None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        size = 0
        for p in (html_path, docx_path):
            if p and p.exists():
                size += p.stat().st_size
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents
                    (doc_id, username, title, document_type, tracking_code,
                     revision, document_status, classification, retention_policy, document_owner, approver,
                     html_path, docx_path, file_size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    username,
                    title,
                    document_type,
                    tracking_code,
                    revision,
                    document_status,
                    classification,
                    retention_policy,
                    document_owner,
                    approver,
                    str(html_path) if html_path else None,
                    str(docx_path) if docx_path else None,
                    size,
                    now,
                ),
            )
            conn.commit()

    def get_document(self, doc_id: str, username: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE doc_id = ? AND username = ?",
                (doc_id, username),
            ).fetchone()
        return dict(row) if row else None

    def list_documents(self, username: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE username = ? ORDER BY created_at DESC",
                (username,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_document(self, doc_id: str, username: str) -> None:
        record = self.get_document(doc_id, username)
        if not record:
            return
        self._delete_files(record)
        with self._connect() as conn:
            conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            conn.commit()

    def purge_expired(self) -> None:
        """Delete records by per-user retention policy and enforce per-user storage limits."""
        now = datetime.now(timezone.utc)
        user_policies: dict[str, tuple[int, bool]] = {}
        with self._connect() as conn:
            user_rows = conn.execute(
                "SELECT username, retention_days, unlimited_storage FROM users"
            ).fetchall()
            for row in user_rows:
                user_policies[str(row["username"])] = (
                    int(row["retention_days"] or DEFAULT_RETENTION_DAYS),
                    bool(row["unlimited_storage"]),
                )

        with self._connect() as conn:
            all_rows = conn.execute("SELECT * FROM documents").fetchall()

        old_rows = []
        for row in all_rows:
            retention_days, _ = user_policies.get(
                str(row["username"]),
                (DEFAULT_RETENTION_DAYS, False),
            )
            cutoff = now - timedelta(days=max(1, retention_days))
            created_at = datetime.fromisoformat(str(row["created_at"]))
            if created_at < cutoff:
                old_rows.append(row)

        for row in old_rows:
            self._delete_files(dict(row))
        if old_rows:
            with self._connect() as conn:
                conn.executemany(
                    "DELETE FROM documents WHERE doc_id = ?",
                    [(r["doc_id"],) for r in old_rows],
                )
                conn.commit()

        # Trim oldest-first per user if storage limit exceeded and user is not unlimited.
        with self._connect() as conn:
            remaining_rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC"
            ).fetchall()

        rows_by_user: dict[str, list[sqlite3.Row]] = {}
        for row in remaining_rows:
            rows_by_user.setdefault(str(row["username"]), []).append(row)

        for username, user_rows in rows_by_user.items():
            _, unlimited_storage = user_policies.get(username, (DEFAULT_RETENTION_DAYS, False))
            if unlimited_storage:
                continue

            total = sum(r["file_size_bytes"] for r in user_rows)
            if total <= DEFAULT_MAX_TOTAL_BYTES:
                continue

            for row in reversed(user_rows):
                if total <= DEFAULT_MAX_TOTAL_BYTES:
                    break
                self._delete_files(dict(row))
                with self._connect() as conn:
                    conn.execute("DELETE FROM documents WHERE doc_id = ?", (row["doc_id"],))
                    conn.commit()
                total -= row["file_size_bytes"]

    @staticmethod
    def _delete_files(record: dict) -> None:
        parent: Path | None = None
        for key in ("html_path", "docx_path"):
            raw = record.get(key)
            if raw:
                p = Path(raw)
                if p.exists():
                    p.unlink()
                parent = p.parent
        if parent and parent.exists() and not any(parent.iterdir()):
            try:
                parent.rmdir()
            except OSError:
                pass
