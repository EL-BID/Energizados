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


def get_current_version() -> str:
    """Read version from pyproject.toml."""
    toml_path = ROOT / "pyproject.toml"
    content = toml_path.read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', content, flags=re.MULTILINE)
    if not m:
        raise RuntimeError("Could not find version in pyproject.toml")
    return m.group(1)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Bump version and update changelog")
    parser.add_argument(
        "--current",
        required=False,
        help="Current version (auto-detected from pyproject.toml if omitted)",
    )
    parser.add_argument(
        "--type",
        required=True,
        choices=["major", "minor", "patch"],
        help="Bump type",
    )
    args = parser.parse_args()

    current = args.current or get_current_version()
    new_version = bump(current, args.type)
    print(f"Bumping {current} → {new_version} ({args.type})")

    update_pyproject(new_version)
    update_version_py(new_version)
    run_git_cliff(f"v{new_version}")


if __name__ == "__main__":
    main()
