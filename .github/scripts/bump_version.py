#!/usr/bin/env python3
"""
Bump version in pyproject.toml and regenerate CHANGELOG.md via git-cliff.

Usage:
    python bump_version.py --current 0.2.3 --type minor
    python bump_version.py --current 0.2.3 --type patch
    python bump_version.py --current 0.2.3 --type major

Outputs: updated pyproject.toml, src/energizados/_version.py, CHANGELOG.md
"""

from __future__ import annotations

import argparse  # nosec
import re
import subprocess  # nosec B404
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]  # noqa: F401

ROOT = Path(__file__).parent.parent.parent


# ----------------------------------------------------------------------
# Semantic versioning
# ----------------------------------------------------------------------
def bump(version: str, kind: str) -> str:
    major, minor, patch = map(int, version.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    elif kind == "minor":
        return f"{major}.{minor + 1}.0"
    else:
        return f"{major}.{minor}.{patch + 1}"


# ----------------------------------------------------------------------
# Filesystem helpers
# ----------------------------------------------------------------------
def update_pyproject(version: str) -> None:
    toml_path = ROOT / "pyproject.toml"
    content = toml_path.read_text()
    content = re.sub(
        r'^version\s*=\s*"[^"]+"',
        f'version = "{version}"',
        content,
        flags=re.MULTILINE,
    )
    toml_path.write_text(content)
    print(f"Bumped pyproject.toml → {version}")


def update_version_py(version: str) -> None:
    vp = ROOT / "src/energizados/_version.py"
    content = vp.read_text()
    content = re.sub(
        r'^__version__\s*=\s*"[^"]+"',
        f'__version__ = "{version}"',
        content,
        flags=re.MULTILINE,
    )
    vp.write_text(content)
    print(f"Bumped src/energizados/_version.py → {version}")


def run_git_cliff(target_tag: str) -> None:
    """
    Run `git-cliff -t <tag> -o CHANGELOG.md` to regenerate the full changelog
    from the beginning up to (and including) the given tag.
    """
    result = subprocess.run(  # nosec B603 B607
        ["git-cliff", "-t", target_tag, "-o", "CHANGELOG.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("STDERR:", result.stderr, sep="\n")
        raise RuntimeError(f"git-cliff failed: {result.stderr}")
    print("Regenerated CHANGELOG.md via git-cliff")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Bump version and update changelog")
    parser.add_argument(
        "--current",
        required=True,
        help="Current version (read from pyproject.toml if omitted)",
    )
    parser.add_argument(
        "--type",
        required=True,
        choices=["major", "minor", "patch"],
        help="Bump type",
    )
    args = parser.parse_args()

    new_version = bump(args.current, args.type)
    print(f"Bumping {args.current} → {new_version} ({args.type})")

    update_pyproject(new_version)
    update_version_py(new_version)
    run_git_cliff(f"v{new_version}")


if __name__ == "__main__":
    main()
