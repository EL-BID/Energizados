"""Secure pickle utilities with SHA-256 integrity verification and path traversal protection."""

import hashlib
import logging
import pickle  # nosec B403
import warnings
from pathlib import Path

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
    """Save object to pickle and write a SHA-256 hash alongside as <path>.sig.

    The .sig file can be used by secure_load() to verify integrity before
    deserializing.

    Args:
        obj: Object to serialize.
        path: Destination path for the pickle file.
    """
    pkl_path = Path(path)
    with open(pkl_path, "wb") as f:
        pickle.dump(obj, f)  # nosec B301

    sig_path = Path(str(pkl_path) + ".sig")
    sig_path.write_text(_hash_file(pkl_path))
    logger.debug(f"Integrity hash written to: {sig_path}")


def secure_load(path: str, trust_pickle: bool = False):
    """Load a pickle file, verifying SHA-256 integrity if a .sig file exists.

    SECURITY NOTE: Only load pickle files from trusted sources. Even with
    integrity verification, a compromised source can produce a valid .sig file.
    Integrity verification primarily protects against accidental corruption and
    detects unauthorized modifications when the .sig file is kept separately.

    Args:
        path: Path to the pickle file.
        trust_pickle: If True, skip integrity verification entirely.

    Returns:
        Deserialized object.

    Raises:
        ValueError: If the .sig file exists but the hash does not match.
    """
    pkl_path = Path(path)
    sig_path = Path(str(pkl_path) + ".sig")

    if not trust_pickle:
        if sig_path.exists():
            expected = sig_path.read_text().strip()
            actual = _hash_file(pkl_path)
            if actual != expected:
                raise ValueError(
                    f"Pickle integrity check failed for '{path}'. "
                    "The file may have been tampered with or corrupted. "
                    "If you trust this file, pass trust_pickle=True."
                )
            logger.debug(f"Integrity verified for: {path}")
        else:
            warnings.warn(
                f"Loading '{path}' without integrity verification " "(no .sig file found). Only load pickle files from trusted sources.",
                UserWarning,
                stacklevel=2,
            )

    with open(path, "rb") as f:
        return pickle.load(f)  # nosec B301


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
