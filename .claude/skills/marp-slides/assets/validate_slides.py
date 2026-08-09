#!/usr/bin/env python3
"""Validate a Marp-generated presentation for quality and completeness.

Usage:
    python validate_slides.py <input_md> [--output-dir <dir>] [--format pdf|pptx|html]

Exit codes:
    0 — all checks passed
    1 — CRITICAL issues found (presentation likely broken)
    2 — WARNING issues found (presentation works but could be improved)
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckResult:
    level: str  # "CRITICAL" | "WARNING" | "OK"
    rule: str
    message: str


@dataclass
class ValidationResult:
    slides_count: int = 0
    has_frontmatter: bool = False
    has_theme: bool = False
    has_paginate: bool = False
    results: list[CheckResult] = field(default_factory=list)

    @property
    def criticals(self) -> list[CheckResult]:
        return [r for r in self.results if r.level == "CRITICAL"]

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self.results if r.level == "WARNING"]

    @property
    def oks(self) -> list[CheckResult]:
        return [r for r in self.results if r.level == "OK"]


# ── Helpers ─────────────────────────────────────────────────────


def count_slides(content: str) -> int:
    """Count slide separators (---) outside of frontmatter and tables."""
    # Remove YAML frontmatter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3 :]

    # Remove table rows that contain ---
    lines = content.split("\n")
    slide_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            continue
        slide_lines.append(line)

    clean = "\n".join(slide_lines)
    # Count slide separators (--- on its own line)
    separators = re.findall(r"^---\s*$", clean, re.MULTILINE)
    return len(separators) + 1  # N separators = N+1 slides


def has_frontmatter(content: str) -> bool:
    """Check if the file starts with YAML frontmatter (---)."""
    return content.strip().startswith("---")


def has_marp_directive(content: str, directive: str) -> bool:
    """Check if a specific Marp directive exists in frontmatter or comments."""
    # Check frontmatter
    if content.strip().startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            frontmatter = content[3:end]
            if f"{directive}:" in frontmatter or f"{directive} =" in frontmatter:
                return True
    # Check HTML comments
    comments = re.findall(r"<!--.*?-->", content, re.DOTALL)
    for comment in comments:
        if f"{directive}:" in comment or f"{directive} =" in comment:
            return True
    return False


def get_headings(content: str) -> list[str]:
    """Extract all headings from the markdown content."""
    return re.findall(r"^#{1,3}\s+(.+)$", content, re.MULTILINE)


def has_tables(content: str) -> bool:
    """Check if content contains markdown tables."""
    return bool(re.search(r"\|.+\|\s*\n\|[\s\-:|]+\|\s*\n(\|.+\|\s*\n)+", content))


def has_blockquotes(content: str) -> bool:
    """Check if content contains blockquotes."""
    return bool(re.search(r"^>\s+.+$", content, re.MULTILINE))


def check_files_exist(output_dir: Path, base_name: str, fmt: str) -> bool:
    """Check if the output file exists."""
    ext_map = {"pdf": ".pdf", "pptx": ".pptx", "html": ".html"}
    expected = output_dir / f"{base_name}{ext_map[fmt]}"
    return expected.exists()


# ── Validation Rules ────────────────────────────────────────────


def validate_structure(content: str, result: ValidationResult) -> None:
    """Rule: minimum slide count and structure."""
    result.slides_count = count_slides(content)
    if result.slides_count < 3:
        result.results.append(
            CheckResult(
                "CRITICAL",
                "min_slides",
                f"Only {result.slides_count} slide(s) found. Minimum 3 required for a meaningful presentation.",
            )
        )
    elif result.slides_count < 5:
        result.results.append(
            CheckResult(
                "WARNING",
                "min_slides",
                f"{result.slides_count} slides found. Consider adding more for better flow.",
            )
        )
    else:
        result.results.append(
            CheckResult("OK", "min_slides", f"{result.slides_count} slides found.")
        )


def validate_frontmatter(content: str, result: ValidationResult) -> None:
    """Rule: Marp frontmatter with required directives."""
    result.has_frontmatter = has_frontmatter(content)
    if not result.has_frontmatter:
        result.results.append(
            CheckResult(
                "CRITICAL",
                "frontmatter",
                "Missing YAML frontmatter. Marp requires --- delimiters with directives.",
            )
        )
        return

    result.has_theme = has_marp_directive(content, "theme")
    if not result.has_theme:
        result.results.append(
            CheckResult(
                "WARNING",
                "theme",
                "No 'theme' directive found. Using Marp default theme. Consider setting theme: energizados.",
            )
        )
    else:
        result.results.append(CheckResult("OK", "theme", "Theme directive found."))

    result.has_paginate = has_marp_directive(content, "paginate")
    if not result.has_paginate:
        result.results.append(
            CheckResult(
                "WARNING",
                "paginate",
                "No 'paginate' directive. Adding 'paginate: true' provides slide numbers.",
            )
        )
    else:
        result.results.append(CheckResult("OK", "paginate", "Pagination enabled."))


def validate_content_quality(content: str, result: ValidationResult) -> None:
    """Rule: content quality checks."""
    headings = get_headings(content)

    # Check for title slide (h1 as first heading)
    lines = content.lstrip("-").strip().split("\n")
    # Find first non-empty, non-directive line
    first_heading = None
    for line in lines:
        line = line.strip()
        if line.startswith("#"):
            first_heading = line
            break

    if first_heading and first_heading.startswith("# ") and not first_heading.startswith("## "):
        result.results.append(CheckResult("OK", "title_slide", "Title slide detected."))
    else:
        result.results.append(
            CheckResult(
                "WARNING",
                "title_slide",
                "No title slide (h1) detected. Consider adding a title slide as the first slide.",
            )
        )

    # Check heading levels consistency
    h1_count = sum(1 for h in headings if h.startswith("# ") and not h.startswith("## "))
    if h1_count > 2:
        result.results.append(
            CheckResult(
                "WARNING",
                "heading_levels",
                f"{h1_count} h1 headings found. Consider using h1 only for slide titles (use h2 for subtitles).",
            )
        )

    # Check for very long slides (too much text per slide)
    slides = re.split(r"^---\s*$", content, flags=re.MULTILINE)
    # Remove frontmatter if present
    if slides and slides[0].strip().startswith("---"):
        slides = slides[1:]

    long_slides = []
    for i, slide in enumerate(slides):
        # Rough estimate: count non-empty, non-separator lines
        text_lines = [
            ln
            for ln in slide.strip().split("\n")
            if ln.strip()
            and not ln.strip().startswith("<!--")
            and not ln.strip().startswith("|")
            and not ln.strip().startswith("#")
        ]
        if len(text_lines) > 8:
            long_slides.append(i + 1)

    if long_slides:
        result.results.append(
            CheckResult(
                "WARNING",
                "slide_density",
                f"Slides {', '.join(map(str, long_slides))} have >8 content lines. Consider splitting for readability.",
            )
        )


def validate_tables(content: str, result: ValidationResult) -> None:
    """Rule: table quality checks."""
    if not has_tables(content):
        return

    # Check for empty table cells or inconsistent column counts
    table_blocks = re.findall(
        r"(\|.+\|\s*\n\|[\s\-:|]+\|\s*\n(?:\|.+\|\s*\n)+)", content, re.MULTILINE
    )  # noqa: E226  # `-` inside character class is a literal, not subtraction
    for i, table in enumerate(table_blocks):
        rows = [r.strip() for r in table.strip().split("\n") if r.strip()]
        if len(rows) < 3:  # header + separator + at least 1 data row
            result.results.append(
                CheckResult(
                    "WARNING",
                    "table_completeness",
                    f"Table {i + 1} has fewer than 3 rows. Consider adding data or removing the table.",
                )
            )

        # Check column consistency
        col_counts = [
            len(r.split("|")) - 2 for r in rows if not re.match(r"^\|[\s\-:|]+\|$", r)
        ]  # noqa: E226
        if col_counts and len(set(col_counts)) > 1:
            result.results.append(
                CheckResult(
                    "WARNING",
                    "table_alignment",
                    f"Table {i + 1} has inconsistent column counts across rows.",
                )
            )


def validate_output_file(
    output_dir: Path, base_name: str, fmt: str, result: ValidationResult
) -> None:
    """Rule: output file exists and has reasonable size."""
    ext_map = {"pdf": ".pdf", "pptx": ".pptx", "html": ".html"}
    ext = ext_map.get(fmt, ".pdf")
    output_file = output_dir / f"{base_name}{ext}"

    if not output_file.exists():
        result.results.append(
            CheckResult("CRITICAL", "output_file", f"Output file not found: {output_file}")
        )
        return

    size_kb = output_file.stat().st_size / 1024
    min_sizes = {"pdf": 10, "pptx": 20, "html": 5}
    min_size = min_sizes.get(fmt, 5)

    if size_kb < min_size:
        result.results.append(
            CheckResult(
                "CRITICAL",
                "output_size",
                f"Output file is only {size_kb:.1f}KB (minimum {min_size}KB expected). Likely empty or broken.",
            )
        )
    else:
        result.results.append(
            CheckResult("OK", "output_size", f"Output file: {size_kb:.1f}KB. Looks reasonable.")
        )


# ── Main ────────────────────────────────────────────────────────


def validate(
    input_md: Path, output_dir: Path | None = None, fmt: str = "pdf", base_name: str | None = None
) -> ValidationResult:
    """Run all validation checks on a Marp markdown file."""
    content = input_md.read_text(encoding="utf-8")
    result = ValidationResult()

    # Structure checks
    validate_structure(content, result)

    # Frontmatter checks
    validate_frontmatter(content, result)

    # Content quality checks
    validate_content_quality(content, result)

    # Table checks
    validate_tables(content, result)

    # Output file checks (if output_dir provided)
    if output_dir and base_name:
        validate_output_file(output_dir, base_name, fmt, result)

    return result


def print_report(result: ValidationResult) -> None:
    """Print a formatted validation report."""
    print("\n" + "=" * 60)
    print("  MARP SLIDE VALIDATION REPORT")
    print("=" * 60)

    print(f"\n  Slides detected: {result.slides_count}")
    print(f"  Has frontmatter: {result.has_frontmatter}")
    print(f"  Has theme:        {result.has_theme}")
    print(f"  Has paginate:     {result.has_paginate}")

    print("\n  Checks:")
    print("  " + "-" * 56)

    for r in result.results:
        icon = {"CRITICAL": "✗", "WARNING": "⚠", "OK": "✓"}[r.level]
        print(f"  {icon} [{r.level:8s}] {r.rule}: {r.message}")

    print("  " + "-" * 56)

    n_critical = len(result.criticals)
    n_warning = len(result.warnings)
    n_ok = len(result.oks)

    print(f"\n  Summary: {n_ok} OK, {n_warning} warnings, {n_critical} critical")

    if n_critical > 0:
        print("\n  ⛔ FIX critical issues before sharing the presentation.")
    elif n_warning > 0:
        print("\n  ⚠️  Presentation works but could be improved.")
    else:
        print("\n  ✅ All checks passed!")

    print("=" * 60 + "\n")
    return n_critical, n_warning, n_ok


def main():
    parser = argparse.ArgumentParser(description="Validate a Marp presentation for quality")
    parser.add_argument("input_md", help="Path to the Marp markdown file")
    parser.add_argument("--output-dir", help="Directory where the output file was generated")
    parser.add_argument(
        "--format", choices=["pdf", "pptx", "html"], default="pdf", help="Output format to validate"
    )
    parser.add_argument("--base-name", help="Base name of the output file (without extension)")
    args = parser.parse_args()

    input_md = Path(args.input_md)
    if not input_md.exists():
        print(f"ERROR: Input file not found: {input_md}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else None
    base_name = args.base_name or input_md.stem

    result = validate(input_md, output_dir, args.format, base_name)
    n_critical, n_warning, n_ok = print_report(result)

    if n_critical > 0:
        sys.exit(1)
    elif n_warning > 0:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
