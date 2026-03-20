import unicodedata

import pandas as pd


def normalize_text(text: str, replace_null: str = "sin_dato", to_upper: bool = True) -> str:
    if replace_null and pd.isna(text) or text in ("nan", "None", ""):
        return replace_null
    text = str(text).strip()
    if to_upper:
        text = text.upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = " ".join(text.split())
    return text
