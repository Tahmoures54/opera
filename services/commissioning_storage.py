"""Private, tenant-scoped storage for OPERA commissioning evidence."""
from __future__ import annotations

import hashlib
import mimetypes
import os
import uuid
from pathlib import Path

from flask import abort, current_app

# Deliberately narrow allow-list. Executable and active-content formats are rejected.
_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv"}
_MAGIC = {
    ".pdf": lambda data: data.startswith(b"%PDF-"),
    ".png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    ".jpg": lambda data: data.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    ".txt": lambda data: b"\x00" not in data,
    ".csv": lambda data: b"\x00" not in data,
}


def _root() -> Path:
    configured = current_app.config.get("OPERA_UPLOAD_DIR")
    root = Path(configured or (Path(current_app.instance_path) / "uploads")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def store_commissioning_upload(file_storage, *, company_name: str, entity_type: str,
                               entity_id: int, uploaded_by_id: int):
    """Persist a bounded evidence file and return its immutable metadata."""
    if file_storage is None or not file_storage.filename:
        abort(400, description="Choose an evidence file")

    raw_filename = str(file_storage.filename).replace(chr(92), "/")
    filename = "".join(
        character for character in raw_filename.rsplit("/", 1)[-1]
        if character.isprintable() and character not in "/" + chr(92)
    ).strip()
    if not filename or filename in {".", ".."} or len(filename) > 255:
        abort(400, description="Invalid file name")
    extension = Path(filename).suffix.lower()
    if extension not in _ALLOWED_EXTENSIONS:
        abort(400, description="Unsupported evidence file type")

    root = _root()
    tenant_key = hashlib.sha256(company_name.encode("utf-8")).hexdigest()[:24]
    relative_dir = Path(tenant_key) / entity_type.lower() / str(entity_id)
    target_dir = (root / relative_dir).resolve()
    if root not in target_dir.parents:
        abort(400, description="Invalid storage path")
    target_dir.mkdir(parents=True, exist_ok=True)

    token = uuid.uuid4().hex
    stored_name = f"{token}{extension}"
    relative_key = (relative_dir / stored_name).as_posix()
    target = (root / relative_key).resolve()
    if root not in target.parents:
        abort(400, description="Invalid storage path")
    temporary = target.with_suffix(target.suffix + ".part")

    digest = hashlib.sha256()
    size = 0
    prefix = b""
    limit = int(current_app.config.get("MAX_CONTENT_LENGTH") or 10 * 1024 * 1024)
    try:
        with temporary.open("xb") as output:
            while True:
                chunk = file_storage.stream.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    abort(413, description="Evidence file exceeds the upload limit")
                if extension in (".txt", ".csv") and b"\x00" in chunk:
                    abort(400, description="Text evidence cannot contain binary data")
                if len(prefix) < 32:
                    prefix += chunk[:32 - len(prefix)]
                digest.update(chunk)
                output.write(chunk)
        if size == 0 or not _MAGIC[extension](prefix):
            abort(400, description="File content does not match its extension")
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise

    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return {
        "filename": filename,
        "stored_filename": stored_name,
        "storage_key": relative_key,
        "mime_type": mime_type,
        "file_size": size,
        "checksum": digest.hexdigest(),
        "uploaded_by_id": uploaded_by_id,
    }


def resolve_commissioning_upload(storage_key: str) -> Path:
    """Resolve a stored key without allowing traversal outside the evidence root."""
    root = _root()
    candidate = (root / storage_key).resolve()
    if root not in candidate.parents or not candidate.is_file():
        abort(404)
    return candidate
