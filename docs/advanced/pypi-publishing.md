# PyPI Publishing Guide

Guide for configuring the Energizados project for publication on PyPI.

## Table of Contents

1. [Verify Package Name](#verify-package-name)
2. [Create PyPI Account](#create-pypi-account)
3. [Enable Two-Factor Authentication (2FA)](#enable-two-factor-authentication-2fa)
4. [Generate API Token](#generate-api-token)
5. [Configure Local Credentials](#configure-local-credentials)
6. [Prepare pyproject.toml](#prepare-pyprojecttoml)
7. [First Publication](#first-publication)
8. [Automation with GitHub Actions](#automation-with-github-actions)

## Verify Package Name

Before starting, verify that the name `energizados` is available on PyPI.

### Option 1: Web Search

Visit: https://pypi.org/search/?q=energizados

### Option 2: From Terminal

```bash
pip search energizados  # if available
# or visit directly
curl https://pypi.org/pypi/energizados/json
# If returns 404, the name is available
```

!!! warning "Name Availability"

    If the name is NOT available, you must change it in `pyproject.toml`:

    ```toml
    [project]
    name = "energizados-ml"  # or alternative name you choose
    ```

    **Considerations for choosing a name:**
    - Unique on PyPI
    - Easy to remember
    - Representative of the project
    - Avoid conflicts with registered trademarks

## Create PyPI Account

### 1. Register

1. Go to https://pypi.org/account/register/
2. Complete the form:
    - **Username**: Your username (public)
    - **Email**: Valid email (will be verified)
    - **Password**: Secure password

### 2. Verify Email

PyPI will send a verification email. Click the link to activate the account.

## Enable Two-Factor Authentication (2FA)

!!! danger "IMPORTANT"

    PyPI **REQUIRES** 2FA to publish packages.

### Steps to Enable 2FA

1. Log in at https://pypi.org/

2. Go to **Account Settings**: https://pypi.org/manage/account/

3. Find **Two-factor authentication** section

4. Choose method:
    - **TOTP** (recommended): Use authenticator app (Google Authenticator, Authy, etc.)
    - **WebAuthn**: Use hardware key (YubiKey)

5. Scan QR code with your authenticator app

6. Enter 6-digit code to confirm

7. **SAVE RECOVERY CODES** - Necessary if you lose access

!!! tip "Backup Your Recovery Codes"

    Store your recovery codes in a secure location. If you lose access to your 2FA device, you'll need these codes to recover your account.

## Generate API Token

PyPI uses API Tokens for authentication instead of username/password.

### Create an API Token for Entire Account

1. Go to: https://pypi.org/manage/account/token/

2. Click **Add API token**

3. Configure token:
    - **Token name**: `energizados-publishing` (or descriptive)
    - **Scope**: Select **"Entire account"** (to create new packages)

4. Click **Add token**

5. **COPY THE TOKEN NOW**
    ```
    pypi-AGVmAGx... complete token ...
    ```
    
    !!! warning "Token Security"

        The token is only shown ONCE. Save it in a secure place immediately. If you lose it, you'll need to generate a new one.

### Create an API Token for Specific Package (after first publication)

Once the package exists, you can create tokens with limited scope:

1. Go to: https://pypi.org/manage/project/energizados/tokens/

2. **Token name**: `energizados-deploy`

3. **Scope**: Select **"Only this project"**

4. Click **Add token**

## Configure Local Credentials

### Option 1: Use `.pypirc` File (traditional method)

Create or edit `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-AGVmAGx...your-complete-token...

[testpypi]
username = __token__
password = pypi-AGVmAGx...your-complete-token...
repository = https://test.pypi.org/legacy/
```

!!! warning "Security Risk"

    The `.pypirc` file contains credentials in plain text. Consider using environment variables or keyring instead.

### Option 2: Environment Variables (recommended method)

In your shell (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="pypi-AGVmAGx...your-complete-token..."
```

!!! tip "Environment Variables"

    This is the most portable method and works well with CI/CD pipelines.

### Option 3: Keyring (most secure method)

```bash
# Install keyring
pip install keyring

# Save credentials
keyring set https://upload.pypi.org/legacy/ __token__
# Password: pypi-AGVmAGx...your-complete-token...
```

Twine will automatically use the keyring if it exists.

!!! tip "Keyring Advantage"

    Keyring is the most secure method as it stores credentials in your OS's credential manager rather than in plain text files.

## Prepare pyproject.toml

The file should already be configured, but verify:

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "energizados"              # ← Unique name on PyPI
version = "0.1.0"                  # ← First version
description = "Framework for electricity fraud detection"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [
    { name = "Energizados Team", email = "contact@energizados.org" }
]

# Dependencies
dependencies = [
    "boruta==0.4.3",
    "catboost==1.2.8",
    # ... rest of dependencies
]

[project.urls]
Homepage = "https://github.com/EL-BID/energizados"
Documentation = "https://energizados.readthedocs.io"
Repository = "https://github.com/EL-BID/energizados"
Issues = "https://github.com/EL-BID/energizados/issues"
```

### Verify README.md

The README will be used as long description on PyPI. Ensure that:

- Well formatted (Markdown or reStructuredText)
- No relative links
- Images use absolute URLs

!!! tip "README Testing"

    Test your README locally before publishing:
    ```bash
    twine check dist/*
    ```

## First Publication

### 1. Install Publishing Tools

```bash
pip install build twine
```

### 2. Build Packages

```bash
# Make sure you're on the correct branch
git checkout main

# Clean if previous build exists
rm -rf dist/ build/ *.egg-info

# Build
python -m build
```

This creates:

```
dist/
├── energizados-0.1.0.tar.gz      # Source distribution
└── energizados-0.1.0-py3-none-any.whl  # Wheel
```

### 3. Verify Packages

```bash
twine check dist/*
```

Should show:

```
Checking dist/energizados-0.1.0.tar.gz: PASSED
Checking dist/energizados-0.1.0-py3-none-any.whl: PASSED
```

!!! tip "Always Verify"

    Always run `twine check` before uploading. It catches common issues with README formatting and metadata.

### 4. Test on TestPyPI (recommended)

```bash
twine upload --repository testpypi dist/*
```

If it works, test installation:

```bash
pip install --index-url https://test.pypi.org/simple/ energizados
```

!!! tip "TestPyPI"

    TestPyPI is a separate instance of PyPI for testing. Packages uploaded here are not installable from the main PyPI and will be automatically deleted after a period of time.

### 5. Publish to Official PyPI

```bash
twine upload dist/*
```

With configured credentials, it will only ask for confirmation.

!!! danger "Final Check"

    Before uploading to PyPI, make sure:
    - You've tested on TestPyPI
    - The version number is correct
    - All tests pass
    - Documentation is complete

### 6. Verify Publication

Visit: https://pypi.org/project/energizados/

## Automation with GitHub Actions

To automate future publications:

### 1. Create Secret in GitHub

1. Go to repo: https://github.com/EL-BID/energizados/settings/secrets/actions
2. Create new secret:
    - **Name**: `PYPI_API_TOKEN`
    - **Value**: `pypi-AGVmAGx...your-complete-token...`

!!! tip "GitHub Secrets"

    Repository secrets are encrypted and only exposed to GitHub Actions. Never commit secrets to your repository.

### 2. Create Publishing Workflow

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  pypi:
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # REQUIRED for trusted publishing

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.x"

      - name: Install build tools
        run: |
          python -m pip install --upgrade pip
          pip install build twine

      - name: Build package
        run: python -m build

      - name: Check package
        run: twine check dist/*

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

### 3. Use Trusted Publishing (more secure method)

PyPI supports "Trusted Publishing" with OpenID Connect - no API tokens required.

Configure in PyPI:

1. Go to: https://pypi.org/manage/account/publishing/
2. Add new publisher:
    - **PyPI Project Name**: `energizados`
    - **Owner**: `EL-BID`
    - **Repository name**: `energizados`
    - **Workflow name**: `publish.yml`
    - **Environment name**: (leave empty)

And modify the workflow:

```yaml
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
```

!!! tip "Trusted Publishing"

    Trusted Publishing is more secure than using API tokens because it uses OpenID Connect authentication. No secrets need to be stored in GitHub.

## Command Summary

| Command                                     | Description           |
|---------------------------------------------|-----------------------|
| `pip install build twine`                   | Install tools         |
| `python -m build`                           | Build packages        |
| `twine check dist/*`                        | Verify packages       |
| `twine upload --repository testpypi dist/*` | Upload to TestPyPI    |
| `twine upload dist/*`                       | Upload to official PyPI |

## Next Steps

After first publication:

- [ ] Verify installation: `pip install energizados`
- [ ] Create first GitHub Release
- [ ] Configure automation (optional)
- [ ] Use `PUBLISHING.md` for future versions

## References

- [PyPI Packaging Tutorial](https://packaging.python.org/tutorials/packaging-projects/)
- [PyPI API Tokens](https://pypi.org/help/#apitoken)
- [Trusted Publishers](https://docs.pypi.org/trusted-publishers/)
- [Twine Documentation](https://twine.readthedocs.io/)

---

← [Advanced Topics](architecture.md) | [Contributing](contributing.md) →
