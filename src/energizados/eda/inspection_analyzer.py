"""
Inspection Analyzer Module - Energizados EDA Framework.

Phase 4: Analyzes the inspection process for fraud detection.
Understands the hierarchy: TIPO_SERVICO -> ACAO -> CATEGORIA_NOTA
"""

import logging
from typing import Dict, List, Optional

import pandas as pd

from energizados.eda.base import BaseExplorer

logger = logging.getLogger(__name__)


class InspectionAnalyzer(BaseExplorer):
    """
    Analyzes the inspection process data for energy fraud detection.

    Computes detection rates, inspection hierarchy, and identifies
    potential enforcement biases.

    Args:
        config: Configuration dictionary with thresholds:
            - low_detection_rate_threshold: float (default 0.05) - alert if detection rate < 5%

    Example:
        >>> analyzer = InspectionAnalyzer()
        >>> results = analyzer.analyze(
        ...     df,
        ...     tipo_col="TIPO_SERVICO",
        ...     acao_col="ACAO",
        ...     categoria_col="CATEGORIA_NOTA",
        ...     date_col="DAT_OCORRENCIA",
        ...     id_col="CLIENTE"
        ... )
    """

    def analyze(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        tipo_col: Optional[str] = None,
        acao_col: Optional[str] = None,
        categoria_col: Optional[str] = None,
        date_col: Optional[str] = None,
        id_col: Optional[str] = None,
        **kwargs,
    ) -> Dict:
        """
        Analyze inspection data.

        Args:
            df: Input DataFrame with inspection data
            target_col: Not used in this phase (kept for API consistency)
            tipo_col: Service type column name (TIPO_SERVICO)
            acao_col: Action column name (ACAO)
            categoria_col: Category column name (CATEGORIA_NOTA)
            date_col: Date column name for temporal analysis
            id_col: Client ID column for reincidence analysis
            **kwargs: Additional arguments (ignored)

        Returns:
            dict with keys:
                - tipo_distribution: dict of {tipo: count}
                - detection_rate: float - overall fraud detection rate
                - reinspections: dict with reincidence stats
                - temporal_distribution: list of {period, count}
                - hierarchy: dict with tipo->acao->categoria breakdown
        """
        self.alerts = []

        if not any([tipo_col, acao_col, categoria_col]):
            logger.warning("No inspection columns specified, skipping analysis")
            self.results = {}
            return {}

        # Filter to relevant columns
        cols_to_use = [c for c in [tipo_col, acao_col, categoria_col, date_col, id_col] if c and c in df.columns]
        if not cols_to_use:
            logger.warning("No valid inspection columns found in DataFrame")
            self.results = {}
            return {}

        sub = df[cols_to_use].copy()

        results = {}

        # --- Tipo de Serviço distribution ---
        if tipo_col and tipo_col in sub.columns:
            tipo_dist = sub[tipo_col].value_counts().to_dict()
            results["tipo_distribution"] = {str(k): int(v) for k, v in tipo_dist.items()}

        # --- Detection rate (assumption: certain ACAO values indicate fraud found) ---
        if acao_col and acao_col in sub.columns:
            acao_dist = sub[acao_col].value_counts()
            total = len(sub[acao_col].dropna())

            # Heuristic: actions like "IRREGULARIDADE DETECTADA" indicate fraud found
            fraud_indicators = [
                "IRREGULARIDADE",
                "FRAUDE",
                "IRREGULAR",
                "DETECTADA",
                "PROCEDEU",
                "CONFIRMADA",
            ]

            fraud_actions = 0
            for acao, count in acao_dist.items():
                if any(ind in str(acao).upper() for ind in fraud_indicators):
                    fraud_actions += count

            detection_rate = fraud_actions / total if total > 0 else 0.0
            results["detection_rate"] = round(detection_rate, 6)
            results["acao_distribution"] = {str(k): int(v) for k, v in acao_dist.to_dict().items()}

            # Alert if detection rate is too low
            low_threshold = self.config.get("low_detection_rate_threshold", 0.05)
            if detection_rate < low_threshold:
                self._add_alert(
                    code="LOW_DETECTION_RATE",
                    message=(
                        f"La tasa de detección de fraude es baja ({detection_rate:.1%}). "
                        f"Esto podría indicar que las inspecciones no están enfocadas correctamente."
                    ),
                    severity="WARNING",
                    details={"detection_rate": detection_rate, "threshold": low_threshold},
                )

        # --- Reincidence analysis (clients inspected multiple times) ---
        if id_col and id_col in sub.columns:
            id_counts = sub[id_col].value_counts()
            reinspected = (id_counts > 1).sum()

            results["reinspections"] = {
                "total_clients_inspected": int(id_counts.count()),
                "clients_reinspected": int(reinspected),
                "reinspection_rate": round(float(reinspected / id_counts.count()) if id_counts.count() > 0 else 0.0, 4),
                "max_inspections_per_client": int(id_counts.max()) if len(id_counts) > 0 else 0,
            }

        # --- Temporal distribution ---
        if date_col and date_col in sub.columns:
            try:
                if not pd.api.types.is_datetime64_any_dtype(sub[date_col]):
                    sub["_date_parsed"] = pd.to_datetime(sub[date_col], errors="coerce")
                else:
                    sub["_date_parsed"] = sub[date_col]

                sub["_year_month"] = sub["_date_parsed"].dt.to_period("M").astype(str)
                temporal_dist = sub["_year_month"].value_counts().sort_index()

                results["temporal_distribution"] = [{"period": str(k), "count": int(v)} for k, v in temporal_dist.items()]
            except Exception as e:
                logger.debug("Error computing temporal distribution: %s", e)

        # --- Hierarchy breakdown (tipo -> acao -> categoria) ---
        hierarchy = {}
        if tipo_col and tipo_col in sub.columns:
            for tipo in sub[tipo_col].dropna().unique():
                tipo_str = str(tipo)
                hierarchy[tipo_str] = {}

                tipo_subset = sub[sub[tipo_col] == tipo]

                if acao_col and acao_col in tipo_subset.columns:
                    for acao in tipo_subset[acao_col].dropna().unique():
                        acao_str = str(acao)
                        hierarchy[tipo_str][acao_str] = {"count": int((tipo_subset[acao_col] == acao).sum())}

                        if categoria_col and categoria_col in tipo_subset.columns:
                            acao_subset = tipo_subset[tipo_subset[acao_col] == acao]
                            cat_dist = acao_subset[categoria_col].value_counts()
                            hierarchy[tipo_str][acao_str]["categories"] = {str(k): int(v) for k, v in cat_dist.items()}

        results["hierarchy"] = hierarchy

        self.results = results
        return results

    def get_alerts(self) -> List[Dict]:
        """Return list of alerts generated during analysis."""
        return self.alerts
