"""Pickle serialization with SHA-256 integrity verification.

Saves Python objects via ``joblib`` (pickle) and writes a SHA-256 hash to a
sidecar ``.sig`` file, so that :func:`load` can detect corruption or
tampering *before* deserializing.

THREAT MODEL
============

What this protects against
--------------------------

* **Accidental corruption** — bit rot, truncated writes, transfer errors.
  The hash check rejects modified files loudly instead of letting pickle
  produce a silently wrong object.

* **Detection of unauthorized modification when the ``.sig`` is kept
  separately from the ``.pkl``** — e.g. when the ``.pkl`` lives in a shared
  location but the ``.sig`` is delivered out-of-band.

What this does NOT protect against
----------------------------------

* **An active attacker who can write the ``.pkl`` file.** The ``.sig`` is
  written next to the ``.pkl`` by the same writer, so anyone who can
  replace the ``.pkl`` can also produce a matching ``.sig``. The hash is a
  corruption/tamper *detector*, not an *authenticator*.

* **Arbitrary code execution via pickle.** ``joblib.load`` runs arbitrary
  code on deserialization. Integrity verification does not change this.
  Only load files from sources you trust to run code in your process.

* **Path traversal via symlinks.** :func:`validate_no_traversal` blocks
  ``..`` components but does not resolve symlinks; a symlink to an
  externally-signed file will pass the integrity check.

History
-------

This module was renamed from ``secure_pickle`` in issue #42 because the
``secure_`` prefix falsely suggested that pickle deserialization was made
safe against untrusted input. The previous name is no longer importable;
callers must update to ``energizados.core.utils.integrity_pickle``.
"""

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


def dump(obj, path: str) -> None:
    """Save object with joblib and write a SHA-256 hash alongside as ``<path>.sig``.

    The ``.sig`` file can be used by :func:`load` to verify integrity before
    deserializing.

    Args:
        obj: Object to serialize.
        path: Destination path for the file.
    """
    pkl_path = Path(path)
    joblib.dump(obj, pkl_path)

    sig_path = Path(str(pkl_path) + ".sig")
    sig_path.write_text(_hash_file(pkl_path), encoding="utf-8")
    logger.debug(f"Integrity hash written to: {sig_path}")


def load(path: str):
    """Load a joblib file after verifying its SHA-256 integrity signature.

    A ``.sig`` file must exist alongside the file. Use :func:`dump` to
    produce both files together.

    .. warning::

        Integrity verification does NOT make this safe against an attacker
        who can write the ``.pkl`` file. See the THREAT MODEL section at the
        top of this module. Only load files from trusted sources.

    Args:
        path: Path to the serialized file.

    Returns:
        Deserialized object.

    Raises:
        FileNotFoundError: If the ``.sig`` file does not exist.
        ValueError: If the hash does not match the ``.sig`` file.
        ValueError: If path contains directory traversal components.
    """
    validate_no_traversal(path, label="load path")
    pkl_path = Path(path)
    sig_path = Path(str(pkl_path) + ".sig")

    if not sig_path.exists():
        raise FileNotFoundError(
            f"Integrity signature not found for '{path}'. "
            f"Expected '{sig_path}'. Use dump() to generate it."
        )

    expected = sig_path.read_text(encoding="utf-8").strip()
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
