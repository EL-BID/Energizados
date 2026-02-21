"""
Utilidades de visualización para el framework Energizados.

Este módulo contiene funciones para crear gráficos y visualizaciones
comunes en proyectos de Machine Learning.
"""

import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve


def plot_roc(name, labels, predictions, **kwargs):
    """
    Genera una curva ROC.

    Args:
        name: Nombre de la curva (para la leyenda)
        labels: Etiquetas verdaderas (0 o 1)
        predictions: Predicciones de probabilidad
        **kwargs: Argumentos adicionales para plt.plot

    Example:
        >>> plot_roc("Modelo A", y_true, y_proba)
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
