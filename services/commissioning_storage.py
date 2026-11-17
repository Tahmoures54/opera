"""Private, tenant-scoped storage for OPERA commissioning evidence."""
from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
import tempfile
import uuid
from pathlib import Path, PurePosixPath

from flask import abort, current_app

_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv"}
_MAGIC = {
    ".pdf": lambda data: data.startswith(b"%PDF-"),
    ".png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    ".jpg": lambda data: data.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    ".txt": lambda data: b"\x00" not in data,
    ".csv": lambda data: b"\x00" not in data,
}


def _backend() -> str:
    backend = str(current_app.config.get("OPERA_STORAGE_BACKEND", "local")).strip().lower()
    if backend not in {"local", "s3"}:
        abort(503, description="OPERA evidence storage backend is not configured correctly.")
    return backend


def _s3_client():
    """Create an S3-compatible client lazily; IAM credentials are supported."""
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("The S3 evidence backend requires boto3.") from exc
    options = {
        "service_name": "s3",
        "region_name": current_app.config.get("OPERA_S3_REGION") or "us-east-1",
    }
    endpoint = current_app.config.get("OPERA_S3_ENDPOINT_URL")
    access_key = current_app.config.get("OPERA_S3_ACCESS_KEY_ID")
    secret_key = current_app.config.get("OPERA_S3_SECRET_ACCESS_KEY")
    if endpoint:
        options["endpoint_url"] = endpoint
    if access_key:
        options["aws_access_key_id"] = access_key
    if secret_key:
        options["aws_secret_access_key"] = secret_key
    return boto3.client(**options)


def _bucket() -> str:
    bucket = str(current_app.config.get("OPERA_S3_BUCKET") or "").strip()
    if not bucket:
        abort(503, description="Configure OPERA_S3_BUCKET before using durable evidence storage.")
    return bucket


def _object_key(storage_key: str) -> str:
    key_path = PurePosixPath(str(storage_key))
    if key_path.is_absolute() or not key_path.parts or any(part in {"", ".", ".."} for part in key_path.parts):
        abort(400, description="Invalid evidence storage key.")
    prefix = str(current_app.config.get("OPERA_S3_PREFIX") or "opera-evidence").strip("/")
    return f"{prefix}/{key_path.as_posix()}" if prefix else key_path.as_posix()


def _root() -> Path:
    configured = current_app.config.get("OPERA_UPLOAD_DIR")
    root = Path(configured or (Path(current_app.instance_path) / "uploads")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def store_commissioning_upload(file_storage, *, company_name: str, entity_type: str,
                               entity_id: int, uploaded_by_id: int):
    """Validate and persist evidence, returning immutable storage metadata."""
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

    backend = _backend()
    if backend == "local" and current_app.config.get("IS_SERVERLESS"):
        abort(503, description="Local evidence storage is ephemeral in serverless deployments. Configure the S3-compatible OPERA storage backend.")

    tenant_key = hashlib.sha256(company_name.encode("utf-8")).hexdigest()[:24]
    relative_dir = PurePosixPath(tenant_key) / entity_type.lower() / str(entity_id)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    relative_key = (relative_dir / stored_name).as_posix()
    digest = hashlib.sha256()
    size = 0
    prefix = b""
    limit = int(current_app.config.get("MAX_CONTENT_LENGTH") or 10 * 1024 * 1024)

    with tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b") as buffer:
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
            buffer.write(chunk)

        if size == 0 or not _MAGIC[extension](prefix):
            abort(400, description="File content does not match its extension")

        if backend == "s3":
            buffer.seek(0)
            _s3_client().put_object(
                Bucket=_bucket(),
                Key=_object_key(relative_key),
                Body=buffer,
                ContentLength=size,
                ContentType=mimetypes.guess_type(filename)[0] or "application/octet-stream",
                ServerSideEncryption="AES256",
            )
        else:
            root = _root()
            target_dir = (root / Path(relative_dir.as_posix())).resolve()
            if root not in target_dir.parents:
                abort(400, description="Invalid storage path")
            target_dir.mkdir(parents=True, exist_ok=True)
            target = (root / relative_key).resolve()
            if root not in target.parents:
                abort(400, description="Invalid storage path")
            temporary = target.with_suffix(target.suffix + ".part")
            try:
                buffer.seek(0)
                with temporary.open("xb") as output:
                    shutil.copyfileobj(buffer, output, length=64 * 1024)
                os.replace(temporary, target)
            except Exception:
                temporary.unlink(missing_ok=True)
                target.unlink(missing_ok=True)
                raise

    return {
        "filename": filename,
        "stored_filename": stored_name,
        "storage_key": relative_key,
        "mime_type": mimetypes.guess_type(filename)[0] or "application/octet-stream",
        "file_size": size,
        "checksum": digest.hexdigest(),
        "uploaded_by_id": uploaded_by_id,
    }


def read_commissioning_upload(storage_key: str) -> bytes:
    """Read evidence from the configured private backend."""
    if _backend() == "s3":
        try:
            response = _s3_client().get_object(Bucket=_bucket(), Key=_object_key(storage_key))
            return response["Body"].read()
        except Exception as exc:
            error_code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if error_code in {"NoSuchKey", "404", "NotFound"}:
                abort(404)
            raise
    return resolve_commissioning_upload(storage_key).read_bytes()


def delete_commissioning_upload(storage_key: str) -> None:
    """Clean up an object when its database transaction fails."""
    if _backend() == "s3":
        _s3_client().delete_object(Bucket=_bucket(), Key=_object_key(storage_key))
    else:
        resolve_commissioning_upload(storage_key).unlink(missing_ok=True)


def resolve_commissioning_upload(storage_key: str) -> Path:
    """Resolve a local storage key without allowing traversal outside the root."""
    if _backend() != "local":
        abort(500, description="A filesystem path is not available for remote evidence storage.")
    root = _root()
    candidate = (root / storage_key).resolve()
    if root not in candidate.parents or not candidate.is_file():
        abort(404)
    return candidate
