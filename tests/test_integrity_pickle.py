"""Tests for integrity_pickle integrity verification."""

import joblib
import pytest

from energizados.core.utils.integrity_pickle import dump, load


@pytest.fixture()
def pkl_file(tmp_path):
    """Returns a helper that writes an object via dump and gives back its path."""

    def _write(obj, name="model.pkl"):
        path = tmp_path / name
        dump(obj, str(path))
        return path

    return _write


class TestDump:
    def test_creates_pkl_and_sig(self, tmp_path):
        path = tmp_path / "obj.pkl"
        dump({"key": "value"}, str(path))

        assert path.exists()
        assert (tmp_path / "obj.pkl.sig").exists()

    def test_sig_is_valid_sha256(self, tmp_path):
        import hashlib

        path = tmp_path / "obj.pkl"
        dump([1, 2, 3], str(path))

        sig = (tmp_path / "obj.pkl.sig").read_text(encoding="utf-8").strip()
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)

        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        assert sig == sha256


class TestLoad:
    def test_roundtrip(self, pkl_file):
        obj = {"model": "lgbm", "score": 0.95}
        path = pkl_file(obj)

        loaded = load(str(path))
        assert loaded == obj

    def test_raises_when_sig_missing(self, tmp_path):
        path = tmp_path / "model.pkl"
        joblib.dump({"x": 1}, path)
        # No .sig file — must raise

        with pytest.raises(FileNotFoundError, match="Integrity signature not found"):
            load(str(path))

    def test_raises_when_sig_tampered(self, pkl_file, tmp_path):
        path = pkl_file({"data": "original"})
        sig_path = tmp_path / "model.pkl.sig"

        # Corrupt the sig
        sig_path.write_text("0" * 64, encoding="utf-8")

        with pytest.raises(ValueError, match="Integrity check failed"):
            load(str(path))

    def test_raises_when_pkl_tampered(self, pkl_file, tmp_path):
        path = pkl_file({"data": "original"})

        # Replace pkl content after signing
        joblib.dump({"data": "tampered"}, path)

        with pytest.raises(ValueError, match="Integrity check failed"):
            load(str(path))
