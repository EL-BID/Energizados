"""Secure serialization utilities with SHA-256 integrity verification and path traversal protection."""

import hashlib
import logging
from pathlib import Path

import joblib

logger = logging.getLogger(__name__)


def _hash_file(path: Path) -> str:
    """Compute SHA-256 hash of a file.

    Args:
        path: Path to the file to hash.

    Returns:
        str: Hexadecimal SHA-256 hash of the file.
    """
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def secure_dump(obj, path: str) -> None:
    """Save object with joblib and write a SHA-256 hash alongside as <path>.sig.

    The .sig file can be used by secure_load() to verify integrity before
    deserializing.

    Args:
        obj: Object to serialize.
        path: Destination path for the file.
    """
    pkl_path = Path(path)
    joblib.dump(obj, pkl_path)

    sig_path = Path(str(pkl_path) + ".sig")
    sig_path.write_text(_hash_file(pkl_path))
    logger.debug(f"Integrity hash written to: {sig_path}")


def secure_load(path: str):
    """Load a joblib file after verifying its SHA-256 integrity signature.

    A `.sig` file must exist alongside the file. Use ``secure_dump()``
    to produce both files together.

    SECURITY NOTE: Only load files from trusted sources. Even with
    integrity verification, a compromised source can produce a valid .sig file.
    Integrity verification primarily protects against accidental corruption and
    detects unauthorized modifications when the .sig file is kept separately.

    Args:
        path: Path to the serialized file.

    Returns:
        Deserialized object.

    Raises:
        FileNotFoundError: If the .sig file does not exist.
        ValueError: If the hash does not match the .sig file.
    """
    pkl_path = Path(path)
    sig_path = Path(str(pkl_path) + ".sig")

    if not sig_path.exists():
        raise FileNotFoundError(
            f"Integrity signature not found for '{path}'. "
            f"Expected '{sig_path}'. Use secure_dump() to generate it."
        )

    expected = sig_path.read_text().strip()
    actual = _hash_file(pkl_path)
    if actual != expected:
        raise ValueError(
            f"Integrity check failed for '{path}'. "
            "The file may have been tampered with or corrupted."
        )
    logger.debug(f"Integrity verified for: {path}")

    return joblib.load(pkl_path)


def validate_no_traversal(path: str, label: str = "path") -> None:
    """Raise ValueError if path contains directory traversal components ('..').

    Args:
        path: File path to validate.
        label: Descriptive label used in error messages.

    Raises:
        ValueError: If the path contains '..' components.
    """
    if ".." in Path(path).parts:
        raise ValueError(f"Path traversal not allowed in {label}: '{path}'")
