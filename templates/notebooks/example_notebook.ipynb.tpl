{
  "cells": [
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "# {{project_name}} - Experimentation Notebook\n",
        "\n",
        "This notebook is designed to experiment with the {{project_name}} project.\n",
        "\n",
        "## Sections\n",
        "\n",
        "1. Data loading\n",
        "2. Exploratory analysis\n",
        "3. Model experimentation\n",
        "4. Results evaluation"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 1. Setup\n",
        "\n",
        "Import project libraries and modules."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": null,
      "metadata": {},
      "outputs": [],
      "source": [
        "# Imports\n",
        "import sys\n",
        "sys.path.append('..')\n",
        "\n",
        "import pandas as pd\n",
        "import numpy as np\n",
        "import matplotlib.pyplot as plt\n",
        "import seaborn as sns\n",
        "\n",
        "# Project imports\n",
        "from {{project_name}}.src.etl import CustomETL\n",
        "from {{project_name}}.src.features import CustomSelector\n",
        "\n",
        "# Visualization settings\n",
        "sns.set_style(\"whitegrid\")\n",
        "plt.rcParams['figure.figsize'] = (12, 6)\n",
        "\n",
        "print(\"Setup complete!\")"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 2. Data Loading\n",
        "\n",
        "Load processed or raw data for analysis."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": null,
      "metadata": {},
      "outputs": [],
      "source": [
        "# Load processed data\n",
        "try:\n",
        "    df = pd.read_parquet('data/processed/dataset.parquet')\n",
        "    print(f\"Data loaded: {df.shape}\")\n",
        "    display(df.head())\n",
        "except FileNotFoundError:\n",
        "    print(\"No processed data found. Run the ETL first.\")"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 3. Exploratory Analysis\n",
        "\n",
        "Perform exploratory data analysis."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": null,
      "metadata": {},
      "outputs": [],
      "source": [
        "# Dataset information\n",
        "if 'df' in locals():\n",
        "    print(\"\\n--- Dataset Information ---\")\n",
        "    print(df.info())\n",
        "    \n",
        "    print(\"\\n--- Descriptive Statistics ---\")\n",
        "    display(df.describe())\n",
        "    \n",
        "    print(\"\\n--- Null Values ---\")\n",
        "    display(df.isnull().sum())"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 4. Model Experimentation\n",
        "\n",
        "Try different model configurations."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": null,
      "metadata": {},
      "outputs": [],
      "source": [
        "# Example: Train a simple model\n",
        "if 'df' in locals():\n",
        "    # Separate features and target\n",
        "    # Adjust this according to your dataset\n",
        "    # X = df.drop('target', axis=1)\n",
        "    # y = df['target']\n",
        "    \n",
        "    print(\"Define your X and y to train models\")"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 5. Save Results\n",
        "\n",
        "Save results and visualizations."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": null,
      "metadata": {},
      "outputs": [],
      "source": [
        "# Save figures or results\n",
        "# plt.savefig('reports/figura_01.png')\n",
        "print(\"Notebook ready for experimentation!\")"
      ]
    }
  ],
  "metadata": {
    "kernelspec": {
      "display_name": "Python 3",
      "language": "python",
      "name": "python3"
    },
    "language_info": {
      "codemirror_mode": {
        "name": "ipython",
        "version": 3
      },
      "file_extension": ".py",
      "mimetype": "text/x-python",
      "name": "python",
      "nbconvert_exporter": "python",
      "pygments_lexer": "ipython3",
      "version": "3.8.0"
    }
  },
  "nbformat": 4,
  "nbformat_minor": 4
}
