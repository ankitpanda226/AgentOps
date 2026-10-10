"""Utilities for safely uploading and extracting repository zip files."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from uuid import uuid4

UPLOAD_ROOT = "uploads/repos"
MACOS_METADATA_NAMES = {".DS_Store", "__MACOSX"}


def safe_extract_zip(zip_file_path: str, destination_dir: str) -> None:
    """Safely extract a zip file while preventing path traversal."""
    destination = Path(destination_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_file_path) as archive:
        for member in archive.infolist():
            if _is_macos_metadata(member.filename):
                continue
            if _is_symlink(member):
                raise ValueError(f"Refusing to extract symlink: {member.filename}")

            target_path = (destination / member.filename).resolve()
            if target_path != destination and destination not in target_path.parents:
                raise ValueError(f"Unsafe zip path: {member.filename}")

            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target_path.open("wb") as target:
                shutil.copyfileobj(source, target)


def create_repo_upload_dir(original_filename: str) -> dict:
    """Create a unique upload directory and return repo metadata."""
    repo_id = str(uuid4())
    repo_dir = Path(UPLOAD_ROOT) / repo_id
    repo_dir.mkdir(parents=True, exist_ok=True)
    return {
        "repo_id": repo_id,
        "repo_dir": str(repo_dir),
    }


def find_repo_root(extracted_dir: str) -> str:
    """Return a single top-level folder if present, otherwise extracted_dir."""
    root = Path(extracted_dir)
    children = [
        child
        for child in root.iterdir()
        if not _is_macos_metadata(child.name)
    ]
    if len(children) == 1 and children[0].is_dir():
        return str(children[0])
    return str(root)


def _is_macos_metadata(name: str) -> bool:
    parts = Path(name).parts
    return any(part in MACOS_METADATA_NAMES for part in parts)


def _is_symlink(member: zipfile.ZipInfo) -> bool:
    file_type = (member.external_attr >> 16) & 0o170000
    return file_type == 0o120000
