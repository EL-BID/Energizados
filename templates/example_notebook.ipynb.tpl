{
  "cells": [
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "# {{project_name}} - Notebook de Experimentación\n",
        "\n",
        "Este notebook está diseñado para experimentar con el proyecto {{project_name}}.\n",
        "\n",
        "## Secciones\n",
        "\n",
        "1. Carga de datos\n",
        "2. Análisis exploratorio\n",
        "3. Experimentación con modelos\n",
        "4. Evaluación de resultados"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 1. Setup\n",
        "\n",
        "Importar librerías y módulos del proyecto."
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
        "# Imports del proyecto\n",
        "from {{project_name}}.etl import CustomETL\n",
        "from {{project_name}}.models import CustomModel\n",
        "from {{project_name}}.feature_selection import CustomSelector\n",
        "\n",
        "# Configuración de visualizaciones\n",
        "sns.set_style(\"whitegrid\")\n",
        "plt.rcParams['figure.figsize'] = (12, 6)\n",
        "\n",
        "print(\"Setup completado!\")"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 2. Carga de Datos\n",
        "\n",
        "Cargar los datos procesados o crudos para análisis."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": null,
      "metadata": {},
      "outputs": [],
      "source": [
        "# Cargar datos procesados\n",
        "try:\n",
        "    df = pd.read_parquet('data/processed/dataset.parquet')\n",
        "    print(f\"Datos cargados: {df.shape}\")\n",
        "    display(df.head())\n",
        "except FileNotFoundError:\n",
        "    print(\"No hay datos procesados. Ejecuta primero el ETL.\")"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 3. Análisis Exploratorio\n",
        "\n",
        "Realizar análisis exploratorio de datos."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": null,
      "metadata": {},
      "outputs": [],
      "source": [
        "# Información del dataset\n",
        "if 'df' in locals():\n",
        "    print(\"\\n--- Información del Dataset ---\")\n",
        "    print(df.info())\n",
        "    \n",
        "    print(\"\\n--- Estadísticas Descriptivas ---\")\n",
        "    display(df.describe())\n",
        "    \n",
        "    print(\"\\n--- Valores Nulos ---\")\n",
        "    display(df.isnull().sum())"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 4. Experimentación con Modelos\n",
        "\n",
        "Probar diferentes configuraciones de modelos."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": null,
      "metadata": {},
      "outputs": [],
      "source": [
        "# Ejemplo: Entrenar un modelo simple\n",
        "if 'df' in locals():\n",
        "    # Separar features y target\n",
        "    # Ajusta esto según tu dataset\n",
        "    # X = df.drop('target', axis=1)\n",
        "    # y = df['target']\n",
        "    \n",
        "    print(\"Define tu X e y para entrenar modelos\")"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 5. Guardar Resultados\n",
        "\n",
        "Guardar resultados y visualizaciones."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": null,
      "metadata": {},
      "outputs": [],
      "source": [
        "# Guardar figuras o resultados\n",
        "# plt.savefig('reports/figura_01.png')\n",
        "print(\"Notebook listo para experimentación!\")"
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
