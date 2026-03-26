# Energizados Project

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# Energizados specific
data/raw/*
!data/raw/.gitkeep
data/external/*
!data/external/.gitkeep
data/processed/*
!data/processed/.gitkeep
# Training run outputs (each run gets its own dir)
output/train-*/
!output/.gitkeep

# Jupyter
.ipynb_checkpoints/

# Pytest
.pytest_cache/
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db
