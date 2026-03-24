from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from it_doc_builder.config import Settings

MAX_AGE_HOURS = 48
MAX_TOTAL_BYTES = 5 * 1024 ** 3  # 5 GB


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
                    html_path       TEXT,
                    docx_path       TEXT,
                    file_size_bytes INTEGER NOT NULL DEFAULT 0,
                    created_at      TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_document(
        self,
        *,
        doc_id: str,
        username: str,
        title: str,
        document_type: str,
        tracking_code: str,
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
                     html_path, docx_path, file_size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    username,
                    title,
                    document_type,
                    tracking_code,
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
        """Delete records older than MAX_AGE_HOURS and trim to MAX_TOTAL_BYTES."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)).isoformat()
        with self._connect() as conn:
            old_rows = conn.execute(
                "SELECT * FROM documents WHERE created_at < ?", (cutoff,)
            ).fetchall()
        for row in old_rows:
            self._delete_files(dict(row))
        if old_rows:
            with self._connect() as conn:
                conn.executemany(
                    "DELETE FROM documents WHERE doc_id = ?",
                    [(r["doc_id"],) for r in old_rows],
                )
                conn.commit()

        # Trim oldest-first if storage limit exceeded
        with self._connect() as conn:
            all_rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC"
            ).fetchall()
        total = sum(r["file_size_bytes"] for r in all_rows)
        if total <= MAX_TOTAL_BYTES:
            return
        for row in reversed(all_rows):
            if total <= MAX_TOTAL_BYTES:
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
