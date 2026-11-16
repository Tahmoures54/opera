#!/usr/bin/env python3
"""Validate OPERA evidence archives before extracting them."""
from __future__ import annotations

import sys
import tarfile
from pathlib import PurePosixPath


def validate_archive(path: str) -> None:
    """Reject path traversal, links, and special files in an evidence archive."""
    with tarfile.open(path, mode="r:gz") as archive:
        for member in archive.getmembers():
            name = member.name
            archive_path = PurePosixPath(name)
            if archive_path.is_absolute() or ".." in archive_path.parts:
                raise ValueError(f"Unsafe archive path: {name}")
            if member.issym() or member.islnk():
                raise ValueError(f"Links are not permitted in evidence archives: {name}")
            if not (member.isfile() or member.isdir()):
                raise ValueError(f"Unsupported archive entry type: {name}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: validate_evidence_archive.py BACKUP_EVIDENCE.tar.gz")
    try:
        validate_archive(sys.argv[1])
    except (OSError, tarfile.TarError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
