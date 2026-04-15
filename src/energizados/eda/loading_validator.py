"""
Loading Validator Module - Energizados EDA Framework.

Phase 0: Validates data loading quality (encoding, BOM, decimal separators, whitespace).
"""

import logging
import re
from typing import Dict, List, Optional

import pandas as pd

from energizados.eda.base import BaseExplorer

logger = logging.getLogger(__name__)


class LoadingValidator(BaseExplorer):
    """
    Validates CSV/Parquet loading quality issues.

    Detects problems common in Latin American data sources:
    - BOM (Byte Order Mark) in column names
    - Numeric values stored as strings with comma decimal separator
    - Trailing whitespace in categorical columns
    - Encoding issues

    Args:
        config: Configuration dictionary

    Example:
        >>> validator = LoadingValidator()
        >>> results = validator.analyze(df, raw_path="data/raw/file.csv")
        >>> alerts = validator.get_alerts()
    """

    def analyze(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        raw_path: Optional[str] = None,
        encoding_used: str = "utf-8",
        decimal_used: str = ".",
        **kwargs,
    ) -> Dict:
        """
        Validate loading quality of a DataFrame.

        Args:
            df: Loaded DataFrame to validate
            target_col: Not used in this phase (kept for API consistency)
            raw_path: Original file path (used to detect encoding if possible)
            encoding_used: Encoding used to load the file
            decimal_used: Decimal separator used ('.'' or ',')
            **kwargs: Additional arguments (ignored)

        Returns:
            dict with keys:
                - encoding_used: str
                - bom_detected: bool
                - bom_columns: list of column names starting with BOM character
                - numeric_as_string: list of dicts {col, parseable_count, parseable_pct}
                - whitespace_columns: list of dicts {col, affected_count, affected_pct, example}
                - rows_loaded: int
                - decimal_separator: str
        """
        self.alerts = []
        results: Dict = {
            "encoding_used": encoding_used,
            "bom_detected": False,
            "bom_columns": [],
            "numeric_as_string": [],
            "whitespace_columns": [],
            "rows_loaded": len(df),
            "decimal_separator": decimal_used,
        }

        # --- Phase 0.1: BOM detection ---
        bom_cols = [c for c in df.columns if isinstance(c, str) and c.startswith("\ufeff")]
        if bom_cols:
            results["bom_detected"] = True
            results["bom_columns"] = bom_cols
            self._add_alert(
                code="BOM_DETECTED",
                message=(
                    f"Byte Order Mark (BOM) detected in {len(bom_cols)} column name(s). "
                    "This happens when the CSV file was saved with utf-8-sig encoding (Windows). "
                    "Use encoding='utf-8-sig' when loading the file."
                ),
                severity="WARNING",
                details={"bom_columns": bom_cols},
            )

        # --- Phase 0.2: Encoding detection ---
        detected_encoding = self._detect_encoding(raw_path)
        if detected_encoding:
            results["encoding_used"] = detected_encoding
            if detected_encoding.lower() not in ("utf-8", "utf-8-sig", "ascii"):
                self._add_alert(
                    code="BAD_ENCODING",
                    message=(
                        f"File may have non-standard encoding: '{detected_encoding}'. "
                        "Consider using encoding='utf-8-sig' or 'latin-1' as appropriate."
                    ),
                    severity="WARNING",
                    details={"detected_encoding": detected_encoding, "raw_path": raw_path},
                )

        # --- Phase 0.3: Numeric as string detection (comma decimal) ---
        numeric_as_string = []
        # Pattern: digits with comma as decimal separator e.g. "1,234" or "1,23"
        comma_decimal_pattern = re.compile(r"^\d+,\d+$")

        for col in df.columns:
            if df[col].dtype != object:
                continue
            non_null = df[col].dropna()
            if len(non_null) == 0:
                continue

            # Count values matching the comma-decimal pattern
            parseable_mask = non_null.astype(str).str.match(comma_decimal_pattern)
            parseable_count = int(parseable_mask.sum())
            parseable_pct = parseable_count / len(non_null)

            if parseable_pct > 0.5:
                numeric_as_string.append(
                    {
                        "col": col,
                        "parseable_count": parseable_count,
                        "parseable_pct": round(parseable_pct * 100, 2),
                    }
                )

        results["numeric_as_string"] = numeric_as_string
        if numeric_as_string:
            cols_list = [d["col"] for d in numeric_as_string]
            self._add_alert(
                code="NUMERIC_AS_STRING",
                message=(
                    f"{len(numeric_as_string)} column(s) appear numeric but are stored as "
                    f"string with comma decimal separator: {cols_list}. "
                    "Use decimal=',' when loading the CSV or convert them manually."
                ),
                severity="WARNING",
                details={"columns": numeric_as_string},
            )

        # --- Phase 0.4: Whitespace in categorical columns ---
        whitespace_columns = []
        for col in df.columns:
            if df[col].dtype != object:
                continue
            non_null = df[col].dropna()
            if len(non_null) == 0:
                continue

            # Find values where strip() changes the value
            str_vals = non_null.astype(str)
            affected_mask = str_vals != str_vals.str.strip()
            affected_count = int(affected_mask.sum())
            affected_pct = affected_count / len(non_null)

            if affected_count > 0:
                # Get an example of a whitespace-padded value
                examples = str_vals[affected_mask]
                example = examples.iloc[0] if len(examples) > 0 else ""

                whitespace_columns.append(
                    {
                        "col": col,
                        "affected_count": affected_count,
                        "affected_pct": round(affected_pct * 100, 2),
                        "example": repr(example),
                    }
                )

        results["whitespace_columns"] = whitespace_columns
        if whitespace_columns:
            cols_list = [d["col"] for d in whitespace_columns]
            self._add_alert(
                code="WHITESPACE_IN_VALUES",
                message=(
                    f"{len(whitespace_columns)} column(s) have values with leading or trailing whitespace: "
                    f"{cols_list}. Use str.strip() to clean them."
                ),
                severity="INFO",
                details={"columns": whitespace_columns},
            )

        self.results = results
        return results

    def get_alerts(self) -> List[Dict]:
        """Return list of alerts generated during analysis."""
        return self.alerts

    def _detect_encoding(self, raw_path: Optional[str]) -> Optional[str]:
        """
        Try to detect encoding of a raw file using chardet.

        Args:
            raw_path: Path to the raw file

        Returns:
            Detected encoding string or None if detection fails/chardet not available
        """
        if not raw_path:
            return None

        try:
            import chardet

            with open(raw_path, "rb") as f:
                raw_bytes = f.read(100_000)  # Read first 100KB for detection

            detection = chardet.detect(raw_bytes)
            encoding = detection.get("encoding")
            confidence = detection.get("confidence", 0)

            logger.debug("Encoding detection: %s (confidence: %.2f)", encoding, confidence)

            if encoding and confidence > 0.5:
                return encoding
        except ImportError:
            logger.debug("chardet not available, skipping encoding detection")
        except OSError as e:
            logger.debug("Could not read file for encoding detection: %s", e)

        return None
