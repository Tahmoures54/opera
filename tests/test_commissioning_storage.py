from hashlib import sha256
from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import HTTPException

from services import commissioning_storage as storage


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.put_calls = []

    def put_object(self, **kwargs):
        body = kwargs["Body"].read()
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = body
        self.put_calls.append(kwargs)

    def get_object(self, **kwargs):
        return {"Body": BytesIO(self.objects[(kwargs["Bucket"], kwargs["Key"])])}

    def delete_object(self, **kwargs):
        self.objects.pop((kwargs["Bucket"], kwargs["Key"]), None)


def _upload(content=b"%PDF-1.7\nvalid evidence", filename="evidence.pdf"):
    return FileStorage(stream=BytesIO(content), filename=filename)


def test_s3_backend_stores_reads_and_deletes_private_evidence(app, monkeypatch):
    client = FakeS3()
    monkeypatch.setattr(storage, "_s3_client", lambda: client)
    app.config.update(
        OPERA_STORAGE_BACKEND="s3",
        OPERA_S3_BUCKET="opera-private",
        OPERA_S3_PREFIX="projects/evidence",
        OPERA_S3_REGION="eu-central-1",
        IS_SERVERLESS=True,
    )

    with app.app_context():
        metadata = storage.store_commissioning_upload(
            _upload(), company_name="Contractor A", entity_type="CheckSheet",
            entity_id=42, uploaded_by_id=7,
        )
        key = ("opera-private", "projects/evidence/" + metadata["storage_key"])
        assert client.objects[key] == b"%PDF-1.7\nvalid evidence"
        assert client.put_calls[0]["ServerSideEncryption"] == "AES256"
        assert metadata["checksum"] == sha256(client.objects[key]).hexdigest()
        assert storage.read_commissioning_upload(metadata["storage_key"]) == client.objects[key]
        storage.delete_commissioning_upload(metadata["storage_key"])
        assert key not in client.objects


def test_serverless_rejects_ephemeral_local_evidence_storage(app):
    app.config.update(OPERA_STORAGE_BACKEND="local", IS_SERVERLESS=True)
    with app.app_context(), pytest.raises(HTTPException) as error:
        storage.store_commissioning_upload(
            _upload(), company_name="Contractor A", entity_type="CheckSheet",
            entity_id=42, uploaded_by_id=7,
        )
    assert error.value.code == 503


def test_local_backend_remains_available_for_persistent_development(app, tmp_path):
    app.config.update(
        OPERA_STORAGE_BACKEND="local",
        OPERA_UPLOAD_DIR=str(tmp_path),
        IS_SERVERLESS=False,
    )
    with app.app_context():
        metadata = storage.store_commissioning_upload(
            _upload(), company_name="Contractor A", entity_type="CheckSheet",
            entity_id=42, uploaded_by_id=7,
        )
        assert storage.read_commissioning_upload(metadata["storage_key"]) == b"%PDF-1.7\nvalid evidence"
        storage.delete_commissioning_upload(metadata["storage_key"])
        with pytest.raises(HTTPException) as error:
            storage.read_commissioning_upload(metadata["storage_key"])
        assert error.value.code == 404


def test_storage_key_rejects_path_traversal(app):
    app.config.update(OPERA_STORAGE_BACKEND="s3", OPERA_S3_BUCKET="opera-private")
    with app.app_context(), pytest.raises(HTTPException) as error:
        storage._object_key("../outside.pdf")
    assert error.value.code == 400
