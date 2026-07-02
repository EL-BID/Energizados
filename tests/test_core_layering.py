"""Core layering tests — verify core has zero module-level edges to concrete packages."""

import ast
import subprocess  # nosec
import sys
from pathlib import Path


def test_core_has_no_module_level_imports_to_concrete_packages():
    """
    Scan ALL Python files under src/energizados/core/ (including steps/ and builders/)
    and verify ZERO module-level imports from core to concrete packages.

    Forbidden prefixes (cycle-forming):
      - energizados.etl
      - energizados.evaluation
      - energizados.inference
      - energizados.modeling
      - energizados.feature_engineering

    Allowed (not a cycle):
      - energizados.eda (eda does NOT import core at module level)
      - energizados.contracts (leaf package, no energizados imports)

    AST top-level-only scan automatically excludes in-method lazy imports.
    """
    core_root = Path("src/energizados/core")
    forbidden_prefixes = {
        "energizados.etl",
        "energizados.evaluation",
        "energizados.inference",
        "energizados.modeling",
        "energizados.feature_engineering",
    }

    violations = []

    for py_file in core_root.rglob("*.py"):
        source = py_file.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            # Only check top-level imports (not nested inside functions/classes)
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue

            # Check if node is at module level (parent is Module)
            # AST walk doesn't expose parent directly; use line number heuristic
            # We'll collect all and filter by indentation later
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name.startswith(prefix) for prefix in forbidden_prefixes):
                        violations.append((py_file, alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.module and any(
                    node.module.startswith(prefix) for prefix in forbidden_prefixes
                ):
                    violations.append((py_file, node.module, node.lineno))

    # Filter violations to only module-level imports (line number heuristic)
    # Module-level imports are at indentation level 0 (no leading whitespace)
    actual_violations = []
    for file_path, module_name, lineno in violations:
        source = file_path.read_text()
        lines = source.split("\n")
        if lineno <= len(lines):
            line = lines[lineno - 1]
            # Check if it's at module level (no leading whitespace)
            if line == line.lstrip():
                actual_violations.append((file_path, module_name, lineno))

    # Format violations for clear output
    formatted_violations = [
        f"({f.relative_to(Path('src/energizados'))}, '{mod}', {lineno})"
        for f, mod, lineno in actual_violations
    ]

    assert (
        len(actual_violations) == 0
    ), f"Found {len(actual_violations)} module-level imports to concrete packages:\n" + "\n".join(
        formatted_violations
    )


def test_eda_import_remains_unchanged():
    """
    Verify that core/builders/eda_builder.py:11 still imports DatasetExplorer.
    This edge is intentionally NOT a cycle (eda does not import core).
    """
    eda_builder = Path("src/energizados/core/builders/eda_builder.py")
    source = eda_builder.read_text()

    assert (
        "from energizados.eda.dataset_explorer import DatasetExplorer" in source
    ), "eda_builder.py should still import DatasetExplorer (not a cycle, leave as-is)"


def test_core_import_paths():
    """
    Verify public import paths still work after BaseETL repoint to contracts.
    """
    # Core import path works
    from energizados.core import BaseETL

    # BaseETL now sourced from contracts
    assert (
        BaseETL.__module__ == "energizados.contracts"
    ), f"BaseETL should be sourced from contracts, got {BaseETL.__module__}"

    # Legacy path still works (shim re-export)
    from energizados.etl.base import BaseETL as BaseETLFromShim

    assert BaseETLFromShim is BaseETL, "Shim re-export should return same BaseETL"

    # Direct contracts import works
    from energizados.contracts import BaseETL as BaseETLFromContracts

    assert BaseETLFromContracts is BaseETL, "Direct contracts import should return same BaseETL"


def test_core_module_load_does_not_trigger_concrete_imports():  # noqa: S604
    """
    Verify that importing energizados.core does NOT trigger concrete package imports.
    """
    # Test in a fresh subprocess to ensure clean state
    result = subprocess.run(  # nosec
        [
            sys.executable,
            "-c",
            """
import sys
import energizados.core

concrete_packages = [
    'energizados.etl',
    'energizados.evaluation',
    'energizados.inference',
    'energizados.modeling',
    'energizados.feature_engineering',
]

loaded = [pkg for pkg in concrete_packages if pkg in sys.modules]
if loaded:
    print(f"Loaded: {loaded}")
    sys.exit(1)
else:
    print("OK: No concrete packages loaded")
    sys.exit(0)
""",
        ],
        capture_output=True,
        text=True,
    )

    assert (
        result.returncode == 0
    ), f"Importing energizados.core should not load concrete packages. stdout: {result.stdout}, stderr: {result.stderr}"


def test_lazy_imports_behavior_preserved():
    """
    Verify each builder's behavior is unchanged after lazy imports.
    """
    # Test ETLBuilder
    from energizados.core.builders.etl_builder import ETLBuilder

    builder = ETLBuilder()
    # Mock config with minimal required fields
    etl_config = {
        "etl": {
            "sample": {
                "enabled": True,
                "input": "data/raw/test.parquet",
                "output": "data/processed/test.parquet",
                "custom_class": "energizados.etl.pipeline.SourceETL",
                "params": {"mode": "concat"},
                "depends_on": [],
            }
        }
    }

    step = builder.build(etl_config)
    assert step is not None, "ETLBuilder should build a step"

    # Test EvaluationBuilder
    from energizados.core.builders.evaluation_builder import EvaluationBuilder

    eval_builder = EvaluationBuilder()
    eval_config = {
        "evaluation": {
            "enabled": True,
            "input_path": "data/processed/test.parquet",
            "threshold": 0.5,
            "metrics": ["auc", "precision"],
            "generate_plots": False,
            "generate_html_report": False,
            "generate_json_report": False,
        }
    }

    eval_step = eval_builder.build(eval_config)
    assert eval_step is not None, "EvaluationBuilder should build a step"

    # Test InferenceBuilder
    from energizados.core.builders.inference_builder import InferenceBuilder

    infer_builder = InferenceBuilder()
    infer_config = {
        "inference": {
            "enabled": True,
            "input_path": "data/processed/test.parquet",
            "output_path": "output/inference_results.csv",
        }
    }

    infer_step = infer_builder.build(infer_config)
    assert infer_step is not None, "InferenceBuilder should build a step"
