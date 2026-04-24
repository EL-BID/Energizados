#!/usr/bin/env python3
"""
Update the [Unreleased] section of CHANGELOG.md with commits that have been
pushed to main since the last tag.

This script is called by .github/workflows/release.yml on every push to main
(when the push is NOT a version tag) so that the changelog stays fresh without
requiring a release.

Usage:
    python update_changelog.py
"""

from __future__ import annotations

import re
import subprocess  # nosec B404
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

COMMIT_TYPES = {
    "feat": "Added",
    "fix": "Fixed",
    "refactor": "Changed",
    "perf": "Changed",
    "revert": "Removed",
    "docs": None,
    "style": None,
    "test": None,
    "chore": None,
    "ci": None,
    "build": None,
}


def parse_commit(line: str):
    line = re.sub(r"^[a-f0-9]+ ", "", line)
    m = re.match(r"(\w+)(?:\(([^)]+)\))?:\s*(.+)", line)
    if not m:
        return None
    return m.group(1), m.group(2) or "", m.group(3)


def collect_commits_since_last_tag():
    cmd = ["git", "log", "--tags", "--format=%s", "--since", "1 month ago", "--no-merges"]
    result = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603
    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line or line.startswith("chore(release)"):
            continue
        parsed = parse_commit(line)
        if parsed:
            commits.append(parsed)
    return commits


def update_unreleased_section(commits):
    changelog_path = ROOT / "CHANGELOG.md"
    content = changelog_path.read_text()

    sections: dict[str, list[str]] = {}
    for ctype, scope, msg in commits:
        section = COMMIT_TYPES.get(ctype)
        if section is None:
            continue
        sections.setdefault(section, [])
        prefix = f"**{scope}:** " if scope else ""
        sections[section].append(f"- {prefix}{msg}")

    unreleased_marker = "## [Unreleased]"
    if unreleased_marker not in content:
        print("No [Unreleased] section found in CHANGELOG.md — skipping.")
        return

    # Build the new unreleased block
    block_lines = [unreleased_marker, ""]
    for section, bullets in sections.items():
        block_lines.append(f"### {section}")
        block_lines.extend(bullets)
        block_lines.append("")

    new_block = "\n".join(block_lines)

    # Replace everything between [Unreleased] and the next ## [...] or EOF
    pattern = re.compile(r"## \[Unreleased\].*?(?=\n## \[|\Z)", re.DOTALL)
    content = pattern.sub(new_block.rstrip() + "\n", content)

    changelog_path.write_text(content)
    print(f"Updated [Unreleased] section with {len(commits)} commits.")


def main():
    commits = collect_commits_since_last_tag()
    if commits:
        update_unreleased_section(commits)
    else:
        print("No new conventional commits found — no changelog update needed.")


if __name__ == "__main__":
    main()
