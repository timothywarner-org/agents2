"""
File system utilities for safe file handling.

Provides atomic file operations that work correctly on Windows.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Union


def ensure_dirs(*paths: Union[str, Path]) -> None:
    """Ensure directories exist, creating them if necessary.

    Args:
        *paths: Directory paths to ensure exist.
    """
    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)


def get_timestamped_filename(
    base_name: str,
    extension: str = ".json",
    include_date: bool = True,
) -> str:
    """Generate a filename with timestamp.

    Args:
        base_name: Base name for the file (e.g., "result_issue-123").
        extension: File extension (default: ".json").
        include_date: Whether to include date portion.

    Returns:
        Filename with timestamp, e.g., "result_issue-123_20240115_143052.json"
    """
    now = datetime.utcnow()

    if include_date:
        timestamp = now.strftime("%Y%m%d_%H%M%S")
    else:
        timestamp = now.strftime("%H%M%S")

    # Clean up base name (remove any existing extension)
    base_name = base_name.rsplit(".", 1)[0] if "." in base_name else base_name

    # Sanitize for filesystem
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)

    return f"{safe_name}_{timestamp}{extension}"


def atomic_move(
    src: Union[str, Path],
    dest_dir: Union[str, Path],
    new_name: str | None = None,
) -> Path:
    """Move a file atomically to a destination directory.

    This ensures the file is either fully moved or not moved at all,
    preventing partial/corrupt files in the destination.

    Args:
        src: Source file path.
        dest_dir: Destination directory.
        new_name: Optional new filename. If None, uses original name.

    Returns:
        Path to the moved file.

    Raises:
        FileNotFoundError: If source file doesn't exist.
        OSError: If move operation fails.
    """
    src_path = Path(src)
    dest_dir_path = Path(dest_dir)

    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {src_path}")

    # Ensure destination directory exists
    ensure_dirs(dest_dir_path)

    # Determine destination filename
    dest_name = new_name if new_name else src_path.name
    dest_path = dest_dir_path / dest_name

    # Handle existing file at destination
    if dest_path.exists():
        # Add suffix to avoid overwriting
        stem = dest_path.stem
        suffix = dest_path.suffix
        counter = 1
        while dest_path.exists():
            dest_path = dest_dir_path / f"{stem}_{counter}{suffix}"
            counter += 1

    # Move the file
    # On Windows, shutil.move handles cross-drive moves correctly
    shutil.move(str(src_path), str(dest_path))

    return dest_path


def safe_write_json(
    data: str,
    dest_path: Union[str, Path],
    encoding: str = "utf-8",
) -> Path:
    """Write JSON data safely using a temporary file.

    Writes to a temp file first, then renames to avoid partial writes.

    Args:
        data: JSON string to write.
        dest_path: Destination file path.
        encoding: File encoding (default: utf-8).

    Returns:
        Path to the written file.
    """
    dest = Path(dest_path)

    # Ensure parent directory exists
    ensure_dirs(dest.parent)

    # Write to temp file first
    temp_path = dest.with_suffix(dest.suffix + ".tmp")

    try:
        with open(temp_path, "w", encoding=encoding) as f:
            f.write(data)

        # Rename to final destination (atomic on most filesystems)
        # On Windows, we need to remove destination first if it exists
        if dest.exists():
            dest.unlink()
        temp_path.rename(dest)

        return dest

    except Exception:
        # Clean up temp file on failure
        if temp_path.exists():
            temp_path.unlink()
        raise


def get_unique_path(path: Union[str, Path]) -> Path:
    """Get a unique path by adding a counter if the path exists.

    Args:
        path: Desired file path.

    Returns:
        Unique path (original if available, or with counter suffix).
    """
    path = Path(path)

    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 1
    while path.exists():
        path = parent / f"{stem}_{counter}{suffix}"
        counter += 1

    return path
