import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve


def plot_roc(name, labels, predictions, **kwargs):
    fp, tp, _ = roc_curve(labels, predictions)

    plt.plot(100 * fp, 100 * tp, label=name, linewidth=2, **kwargs)
    plt.xlabel("False positives [%]")
    plt.ylabel("True positives [%]")
    plt.xlim([0, 100])
    plt.ylim([0, 100.5])
    plt.grid(True)
    ax = plt.gca()
    ax.set_aspect("equal")
