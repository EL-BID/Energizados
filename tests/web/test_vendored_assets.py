"""
Tests for vendored web console static assets (offline operation).

The web console must work with zero external network requests: all
third-party frontend libraries are vendored under static/vendor/.
"""

import re
from pathlib import Path

from energizados.web import app as web_app

STATIC_DIR = Path(web_app.__file__).parent / "static"
VENDOR_DIR = STATIC_DIR / "vendor"
BASE_TEMPLATE = Path(web_app.__file__).parent / "templates" / "base.html"

REQUIRED_VENDOR_FILES = [
    "htmx.min.js",
    "plotly-2.27.0.min.js",
    "bootstrap.min.css",
    "bootstrap.bundle.min.js",
    "bootstrap-icons/bootstrap-icons.min.css",
    "bootstrap-icons/fonts/bootstrap-icons.woff2",
    "bootstrap-icons/fonts/bootstrap-icons.woff",
    "inter/inter.css",
]


class TestVendoredAssets:
    """Test suite for the vendored static assets of the web console."""

    def test_required_vendor_files_exist(self):
        """All third-party libraries are vendored on disk (non-empty)."""
        for rel_path in REQUIRED_VENDOR_FILES:
            file_path = VENDOR_DIR / rel_path
            assert file_path.is_file(), f"Missing vendored asset: {rel_path}"
            assert file_path.stat().st_size > 0, f"Empty vendored asset: {rel_path}"

    def test_inter_css_uses_local_fonts(self):
        """The vendored Inter css references local woff2 files, not Google Fonts."""
        css = (VENDOR_DIR / "inter" / "inter.css").read_text(encoding="utf-8")
        assert "@font-face" in css
        # No network font source (the header comment cites the origin URL only)
        assert "url(https://" not in css
        assert "url(./inter-" in css

    def test_base_template_has_no_external_references(self):
        """base.html loads every script/stylesheet from the local static dir."""
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        external = re.search(r'(?:src|href)="https?://', template)
        assert external is None, f"External reference found in base.html: {external.group(0)}"

    def test_base_template_references_vendored_assets(self):
        """base.html points at the vendored libraries via the static URL pattern."""
        template = BASE_TEMPLATE.read_text(encoding="utf-8")
        # Assets loaded directly by the template (fonts are reached through
        # their css files' relative ./fonts/ and ./ paths instead).
        direct_refs = [
            "vendor/htmx.min.js",
            "vendor/plotly-2.27.0.min.js",
            "vendor/bootstrap.min.css",
            "vendor/bootstrap.bundle.min.js",
            "vendor/bootstrap-icons/bootstrap-icons.min.css",
            "vendor/inter/inter.css",
        ]
        for rel_path in direct_refs:
            assert rel_path in template, f"base.html does not reference {rel_path}"

    def test_bootstrap_icons_css_references_local_fonts(self):
        """bootstrap-icons.min.css keeps its relative ./fonts/ layout working."""
        css = (VENDOR_DIR / "bootstrap-icons" / "bootstrap-icons.min.css").read_text(
            encoding="utf-8"
        )
        assert "url(" in css
        assert "jsdelivr" not in css
