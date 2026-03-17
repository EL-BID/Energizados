# Installation

This guide will help you install Energizados and get it ready for use.

## Prerequisites

> ⚠️ **IMPORTANT:** Always use a virtual environment for Python projects. Never install packages in your global Python installation. Virtual environments isolate dependencies, prevent version conflicts, and make it easy to clean up.

### Python >= 3.10

Energizados requires Python 3.10 or higher. Verify your current version:

```bash
python --version
```

**If you need to install or update Python:**

**macOS:**

- With Homebrew:
  ```bash
  brew install python@3.11
  ```

- With pyenv:
  ```bash
  pyenv install 3.11.0
  pyenv global 3.11.0
  ```

**Linux (Ubuntu/Debian):**

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv
```

**Windows:**

- Download from [python.org](https://www.python.org/downloads/)
- Or from Microsoft Store: Search for "Python 3.11" or higher

### pip updated

Ensure you have the latest pip:

```bash
python -m pip install --upgrade pip
```

## Installation

> ⚠️ **IMPORTANT: Always use a virtual environment.** Never install packages in your global Python installation. Virtual environments isolate dependencies, prevent version conflicts, and make it easy to clean up. This guide assumes you're using a virtual environment.

### Step 1: Create a Virtual Environment

Choose one of the following methods:

#### Option A: venv (built-in, recommended)

The simplest option — no additional tools required.

**macOS / Linux:**

```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows:**

```cmd
python -m venv .venv
.venv\Scripts\activate
```

#### Option B: pyenv + pyenv-virtualenv

Good for managing multiple Python versions.

**macOS:**

```bash
brew install pyenv pyenv-virtualenv

# Add to ~/.zshrc or ~/.bashrc:
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv-virtualenv-init -)"

# Create and activate
pyenv virtualenv 3.11 energizados
pyenv activate energizados
```

**Linux:**

```bash
curl https://pyenv.run | bash

# Add to ~/.bashrc:
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv-virtualenv-init -)"

# Create and activate
pyenv virtualenv 3.11 energizados
pyenv activate energizados
```

**Windows:** Use [pyenv-win](https://github.com/pyenv-win/pyenv-win):

```powershell
Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"
&"./install-pyenv-win.ps1"

pyenv install 3.11.9
pyenv virtualenv 3.11.9 energizados
pyenv activate energizados
```

#### Option C: Conda

If you already use Anaconda or Miniconda.

**macOS / Linux:**

```bash
conda create -n energizados python=3.11
conda activate energizados
```

**Windows:**

```cmd
conda create -n energizados python=3.11
conda activate energizados
```

> 💡 **Tip:** Whichever method you choose, make sure to add the environment folder (`.venv`, `envs/energizados`, etc.) to your `.gitignore` if it's inside your project folder.

### Step 2: Install Energizados

**Basic Installation** (includes LightGBM):

```bash
pip install energizados
```

**With Extras:**

- **CatBoost** (for CatBoost models):
  ```bash
  pip install energizados[catboost]
  ```

- **TensorFlow** (for neural networks and LSTM):
  ```bash
  pip install energizados[tensorflow]
  ```

- **All extras** (CatBoost + TensorFlow):
  ```bash
  pip install energizados[all]
  ```

### Step 3: Verify Installation

Once installed, verify the CLI is available:

```bash
energizados --version
energizados --help
```

If you see the help message, installation was successful.

---

← [Overview](overview.md) | [Quick Start](quickstart.md) →
