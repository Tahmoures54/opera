"""Security tests for evidence backup archive validation."""
import tarfile

import pytest

from scripts.validate_evidence_archive import validate_archive


def _archive(path, name, kind="file"):
    with tarfile.open(path, "w:gz") as archive:
        import io
        member = tarfile.TarInfo(name)
        if kind == "file":
            payload = b"evidence"
            member.size = len(payload)
            archive.addfile(member, io.BytesIO(payload))
        else:
            member.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
            member.linkname = "../../outside"
            archive.addfile(member)


def test_valid_evidence_archive_is_accepted(tmp_path):
    path = tmp_path / "valid.tar.gz"
    _archive(path, "tenant/checksheet/evidence.pdf")
    validate_archive(str(path))


@pytest.mark.parametrize("name", ["../outside.txt", "/etc/passwd", "tenant/../../outside.txt"])
def test_archive_path_traversal_is_rejected(tmp_path, name):
    path = tmp_path / "unsafe.tar.gz"
    _archive(path, name)
    with pytest.raises(ValueError, match="Unsafe archive path"):
        validate_archive(str(path))


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_archive_links_are_rejected(tmp_path, kind):
    path = tmp_path / "linked.tar.gz"
    _archive(path, "tenant/evidence", kind)
    with pytest.raises(ValueError, match="Links are not permitted"):
        validate_archive(str(path))
