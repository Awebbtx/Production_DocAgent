from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from it_doc_builder.config import Settings


class LogoStore:
    max_items = 5
    max_file_size_bytes = 1024 * 1024  # 1 MB

    def __init__(self, settings: Settings) -> None:
        self._dir = settings.output_dir / "logos"
        self._dir.mkdir(parents=True, exist_ok=True)

    def list_logos(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for path in sorted(self._dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
            if not path.is_file():
                continue
            stat = path.stat()
            created_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            rows.append(
                {
                    "filename": path.name,
                    "url": f"/logos/{path.name}",
                    "size_bytes": int(stat.st_size),
                    "created_at": created_at,
                }
            )
        return rows

    def save_logo(self, original_name: str, data: bytes) -> dict[str, object]:
        existing = self.list_logos()
        if len(existing) >= self.max_items:
            raise ValueError(f"Maximum of {self.max_items} logos allowed. Delete one before uploading.")

        if not data:
            raise ValueError("Uploaded file is empty.")
        if len(data) > self.max_file_size_bytes:
            raise ValueError(f"File too large. Max size is {self.max_file_size_bytes // 1024} KB.")

        extension = self._detect_extension(data)
        safe_stem = re.sub(r"[^a-zA-Z0-9]+", "-", Path(original_name).stem).strip("-").lower() or "logo"
        file_name = f"{uuid4().hex[:10]}-{safe_stem}{extension}"
        path = self._dir / file_name
        path.write_bytes(data)

        stat = path.stat()
        return {
            "filename": path.name,
            "url": f"/logos/{path.name}",
            "size_bytes": int(stat.st_size),
            "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }

    def delete_logo(self, file_name: str) -> bool:
        if "/" in file_name or "\\" in file_name or file_name.startswith("."):
            return False
        path = self._dir / file_name
        if not path.exists() or not path.is_file():
            return False
        path.unlink(missing_ok=True)
        return True

    def resolve_logo_path(self, file_name: str) -> Path | None:
        if "/" in file_name or "\\" in file_name or file_name.startswith("."):
            return None
        path = self._dir / file_name
        if not path.exists() or not path.is_file():
            return None
        return path

    @staticmethod
    def _detect_extension(data: bytes) -> str:
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if data.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        raise ValueError("Only PNG or JPG images are allowed.")
