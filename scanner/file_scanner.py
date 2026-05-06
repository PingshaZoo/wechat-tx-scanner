import os
from pathlib import Path
from dataclasses import dataclass
from typing import List
import logging

logger = logging.getLogger("tx_scanner.scanner")


@dataclass
class FileEntry:
    path: str
    size: int
    mtime: float
    extension: str


def _normalize_extension(ext: str) -> str:
    return ext.lower() if ext.startswith(".") else f".{ext.lower()}"


def find_image_files(scan_paths: List[str], extensions: List[str],
                     min_size_kb: int = 5, max_size_mb: int = 20) -> List[FileEntry]:
    """
    Walk through configured scan paths and find all image/dat files.
    Returns a list of FileEntry objects.
    """
    allowed_exts = {_normalize_extension(e) for e in extensions}
    min_size = min_size_kb * 1024
    max_size = max_size_mb * 1024 * 1024
    files: List[FileEntry] = []

    for scan_path in scan_paths:
        root = Path(scan_path).expanduser()
        if not root.exists():
            logger.warning("Scan path does not exist: %s", root)
            continue

        logger.info("Scanning: %s", root)
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.name.startswith("."):
                continue

            ext = file_path.suffix.lower()
            if ext not in allowed_exts:
                continue

            try:
                stat = file_path.stat()
                if stat.st_size < min_size:
                    continue
                if stat.st_size > max_size:
                    logger.debug("Skipping large file: %s (%.1f MB)", file_path, stat.st_size / 1024 / 1024)
                    continue
            except OSError as e:
                logger.debug("Cannot stat %s: %s", file_path, e)
                continue

            files.append(FileEntry(
                path=str(file_path.resolve()),
                size=stat.st_size,
                mtime=stat.st_mtime,
                extension=ext,
            ))

    logger.info("Found %d image files across %d path(s)", len(files), len(scan_paths))
    return files
