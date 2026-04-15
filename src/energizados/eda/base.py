"""
Base Module for EDA (Exploratory Data Analysis) - Energizados Framework.

Defines the abstract base class for all explorers.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import pandas as pd


class BaseExplorer(ABC):
    """
    Abstract base class for all EDA explorers.

    All explorer implementations must inherit from this class and implement
    the analyze() and get_alerts() methods.

    Args:
        config: Configuration dictionary for this explorer

    Example:
        >>> class MyExplorer(BaseExplorer):
        ...     def analyze(self, df, target_col=None, **kwargs):
        ...         return {'result': 'ok'}
        ...     def get_alerts(self):
        ...         return self.alerts
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the explorer.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.alerts: List[Dict] = []
        self.results: Dict = {}

    @abstractmethod
    def analyze(self, df: pd.DataFrame, target_col: Optional[str] = None, **kwargs) -> Dict:
        """
        Analyze the DataFrame and return results.

        Args:
            df: Input DataFrame to analyze
            target_col: Name of target column (optional)
            **kwargs: Additional arguments specific to each implementation

        Returns:
            dict: Analysis results
        """
        pass

    @abstractmethod
    def get_alerts(self) -> List[Dict]:
        """
        Return list of alerts generated during analysis.

        Returns:
            list: List of alert dicts with keys: code, message, severity, details
        """
        pass

    def _add_alert(
        self,
        code: str,
        message: str,
        severity: str = "WARNING",
        details: Optional[Dict] = None,
    ) -> None:
        """
        Add an alert to the alerts list.

        Args:
            code: Alert code (e.g. 'HIGH_MISSING', 'CLASS_IMBALANCE')
            message: Human-readable alert message
            severity: Alert severity - 'ERROR', 'WARNING', or 'INFO'
            details: Optional dictionary with additional details
        """
        if severity not in ("ERROR", "WARNING", "INFO"):
            severity = "WARNING"

        self.alerts.append(
            {
                "code": code,
                "message": message,
                "severity": severity,
                "details": details or {},
            }
        )
