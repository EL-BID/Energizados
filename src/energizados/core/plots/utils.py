"""
Visualization utilities for the Energizados framework.

This module contains functions for creating common plots and visualizations
in Machine Learning projects.
"""

import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve


def plot_roc(name, labels, predictions, **kwargs):
    """Generate an ROC curve.

    Args:
        name: Name of the curve (for legend).
        labels: True labels (0 or 1).
        predictions: Probability predictions.
        **kwargs: Additional arguments for plt.plot.

    Example:
        >>> plot_roc("Model A", y_true, y_proba)
        >>> plt.legend()
        >>> plt.show()
    """
    fp, tp, _ = roc_curve(labels, predictions)

    plt.plot(100 * fp, 100 * tp, label=name, linewidth=2, **kwargs)
    plt.xlabel("False positives [%]")
    plt.ylabel("True positives [%]")
    plt.xlim([0, 100])
    plt.ylim([0, 100.5])
    plt.grid(True)
    ax = plt.gca()
    ax.set_aspect("equal")
