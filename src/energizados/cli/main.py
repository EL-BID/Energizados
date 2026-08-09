"""
Main CLI entry point for Energizados Framework.

This module defines main command and available subcommands.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

import click
from rich.panel import Panel
from rich.tree import Tree

logger = logging.getLogger(__name__)


def _ensure_utf8_stdio() -> None:
    """Reconfigure stdout/stderr to UTF-8 (errors="replace").

    Windows consoles default to a legacy codepage (cp1252, the 'charmap' codec)
    that cannot encode the non-ASCII glyphs the CLI prints (⚡ ✓ ✗ ⚠ →). On a
    non-TTY stdout (e.g. CI log capture) this raises ``UnicodeEncodeError``.
    PEP 540 UTF-8 mode (``PYTHONUTF8=1``) fixes CI; this guard additionally
    protects real Windows users running the CLI in a cp1252 console. Idempotent
    and safe on streams that don't support ``reconfigure`` (test capture buffers
    are skipped because they already report a UTF-8 encoding).
    """
    for _name in ("stdout", "stderr"):
        stream = getattr(sys, _name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        encoding = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
        if encoding == "utf8":  # already UTF-8 — nothing to do
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # Unsupported stream type (some wrappers); leave it as-is.
            pass


def _setup_logging(verbose: int = 0, log_file: Optional[str] = None):
    """
    Configures logging for the CLI.

    Args:
        verbose: Verbosity level (0=WARNING, 1=INFO, 2+=DEBUG)
        log_file: Optional path to log file. If None, only console logging is used.
    """
    from rich.logging import RichHandler

    from energizados.cli import ui

    if verbose == 0:
        level = logging.WARNING
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = []  # Remove existing handlers

    # Configure RichHandler for console
    console_handler = RichHandler(console=ui.console, show_path=False, rich_tracebacks=True)
    console_handler.setLevel(level)
    root_logger.addHandler(console_handler)

    # Add file handler if log_file is specified
    if log_file:
        from pathlib import Path

        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file handler
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setLevel(level)

        # Simple formatter for file (no ANSI codes)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # Log to console that we're writing to file
        ui.console.print(f"[dim]Logging to file: {log_file}[/dim]")

    # Expose handler globally for level management
    ui.set_rich_handler(console_handler)


class EnergizadosGroup(click.Group):
    """Custom Click Group to provide helpful hints for removed commands."""

    def get_command(self, ctx, cmd_name):
        """Override to provide custom hints for removed commands."""
        rv = super().get_command(ctx, cmd_name)
        if rv is not None:
            return rv

        # Check if user is trying to run the removed 'eda' command
        if cmd_name == "eda":
            from energizados.cli.ui import print_error, print_info

            print_error("No such command 'eda'.")
            print_info("")
            print_info("The 'eda' subcommand has been removed.")
            print_info("  Use: energizados run eda")
            raise click.Abort()

        return None


def _output_json(data: Any) -> None:
    """
    Output data as JSON to stdout.

    Args:
        data: Any data structure. If it has a `to_dict()` method, that will be called
              to get a JSON-serializable dict. Otherwise, json.dumps with default=str is used.
    """
    if hasattr(data, "to_dict"):
        data = data.to_dict()
    click.echo(json.dumps(data, indent=2, default=str))


def _print_next_steps(project_name: str):
    """
    Print next steps as a Rich Panel with Tree.

    Args:
        project_name: Name of the created project.
    """
    from energizados.cli.ui import console

    tree = Tree("[bold cyan]✓ Project created successfully![/]")
    tree.add(f"[cyan]1.[/] cd {project_name}")
    edit_config = tree.add("[cyan]2.[/] Edit configuration files in config/:")
    edit_config.add("[cyan]•[/] etl.yaml")
    edit_config.add("[cyan]•[/] train.yaml")
    edit_config.add("[cyan]•[/] infer.yaml")
    edit_config.add("[cyan]•[/] eda.yaml")
    tree.add("[cyan]3.[/] (Optional) Customize src/data/custom_etl.py")
    tree.add("[cyan]4.[/] energizados run eda")
    tree.add("[cyan]5.[/] energizados run etl,train")

    panel = Panel(tree, title="[bold]Next Steps[/]", border_style="cyan")
    console.print("\n")
    console.print(panel)
    console.print()


@click.group(cls=EnergizadosGroup)
@click.version_option(version=None, prog_name="energizados", package_name="energizados")
@click.pass_context
def cli(ctx):
    """
    Energizados - Framework for detecting fraud in energy consumption.

    This framework allows creating ML pipelines for fraud detection
    with simple configuration and extensibility.

    Available commands:
    - init: Initialize a new project
    - run: Execute a pipeline from configuration
    - validate: Validate configuration file
    - doctor: Check system information and validate environment

    For help on a specific command:
        energizados <command> --help
    """
    # Force UTF-8 stdio so non-ASCII glyphs (⚡ ✓ ✗ ⚠ →) don't crash on Windows
    # consoles whose default encoding (cp1252) can't encode them.
    _ensure_utf8_stdio()

    # Shared context between commands
    ctx.ensure_object(dict)


@cli.command()
@click.argument("project_name")
@click.option(
    "--template",
    "-t",
    default="default",
    help="Template to use for the project (default)",
    show_default=True,
)
@click.option(
    "--path",
    "-p",
    default=".",
    help="Directory where to create the project",
    show_default=True,
)
@click.option(
    "--copy",
    "-c",
    "copy_from",
    default=None,
    help="Copy from existing project (takes precedence over --template)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force creation by removing the existing directory if necessary",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help=(
        "Skip interactive prompts. On a directory conflict, recreation also requires "
        "--force (e.g. `init x --yes --force`). Useful for CI/automation."
    ),
)
@click.pass_context
def init(ctx, project_name, template, path, copy_from, force, yes):
    """
    Initialize a new Energizados project.

    This command creates the base structure of a project with all the
    necessary files to customize the pipeline.

    PROJECT_NAME is the name of the project to create.

    Examples:
        energizados init my_project              # Create from template
        energizados init new --copy existing     # Copy from existing project
        energizados init my_project --force      # Replace if exists
        energizados init my_project --yes --force # Non-interactive recreate (CI/automation)
    """
    from energizados.cli.init import create_project
    from energizados.cli.ui import print_error, print_info, print_success

    # Reject traversal-shaped names at the CLI boundary so the operator
    # gets a clear error instead of having ``create_project`` silently
    # slugify their input. The web console relies on ``create_project``'s
    # permissive slugification instead (see ``_slugify_for_filesystem``),
    # which keeps the path confined without breaking the HTTP flow.
    if not project_name or not project_name.strip():
        raise click.BadParameter("Project name must not be empty.")
    if project_name != project_name.strip():
        raise click.BadParameter("Project name must not have leading or trailing whitespace.")
    if ".." in project_name or "/" in project_name or "\\" in project_name:
        raise click.BadParameter(
            "Project name must not contain path separators ('/', '\\') or '..' "
            "(would escape the target directory)."
        )
    if project_name.startswith("."):
        raise click.BadParameter("Project name must not start with '.'.")

    project_path = Path(path) / project_name

    def _do_create(use_force: bool) -> None:
        """Run the create_project + success messages sequence."""
        if use_force:
            print_info("Removing existing directory...")
        create_project(
            project_name=project_name,
            project_path=project_path,
            template=template,
            copy_from=copy_from,
            force=use_force,
        )
        print_success(f"Project created successfully at: {project_path}")
        _print_next_steps(project_name)

    try:
        if copy_from:
            source_path = Path(path) / copy_from
            if not source_path.exists():
                print_error(f"Source project '{copy_from}' does not exist at: {source_path}")
                raise click.Abort()
            print_info(f"Copying project from '{copy_from}'...")
        else:
            print_info(f"Creating project '{project_name}'...")

        _do_create(use_force=force)
    except FileExistsError as e:
        # When --force is set, create_project() at line above already removed and
        # recreated the dir, so this branch is only reached with force=False.
        if yes and not force:
            # --yes without --force is ambiguous on a conflict; refuse rather
            # than silently overwrite.
            print_error(
                f"{e}\n--yes was given without --force; refusing to overwrite "
                "an existing directory. Re-run with --force to recreate."
            )
            raise click.Abort()
        if click.confirm(
            f"\n{e}\nDo you want to delete the existing directory and recreate it?", default=False
        ):
            _do_create(use_force=True)
        else:
            print_error("Operation cancelled.")
            raise click.Abort()
    except ValueError as e:
        # ``create_project`` validates ``project_name`` at the boundary
        # before touching the filesystem. The web console maps ValueError
        # to HTTP 400; here we surface it as a usage error so the CLI
        # shows a clear message and exits with a non-zero status.
        raise click.BadParameter(str(e), param_hint="PROJECT_NAME")
    except Exception as e:
        print_error(f"Error creating project: {e}")
        print_info("Tip: Check the project name and try again")
        raise click.Abort()


@cli.command()
@click.argument("configs", nargs=-1, required=True)
@click.option(
    "--config-path",
    "-p",
    default=None,
    help="Config directory (default: ./config/)",
)
@click.option(
    "--step",
    "-s",
    help="Run only a specific pipeline step (etl, split, train, evaluation, infer)",
)
@click.option(
    "--etl",
    "-e",
    help="Run a specific ETL (and its dependencies). Only valid with multiple ETLs.",
)
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Show what would be executed without actually running (for ETLs shows the execution plan)",
)
@click.option(
    "--json",
    "-j",
    is_flag=True,
    default=False,
    help="Output results as JSON instead of human-readable format",
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase verbosity (-v: INFO, -vv/-vvv: DEBUG)",
)
@click.option(
    "--name",
    "-n",
    default=None,
    help="Custom run directory name (default: auto-generated timestamp)",
)
@click.option(
    "--overwrite",
    "-o",
    is_flag=True,
    default=False,
    help="Overwrite existing output directory if it exists",
)
@click.option(
    "--log-file",
    "-l",
    default=None,
    help="Path to log file (default: <run_dir>/run.log)",
)
@click.pass_context
def run(ctx, configs, config_path, step, etl, dry_run, json, verbose, name, overwrite, log_file):
    """
    Execute a pipeline from YAML configuration.

    This command reads the configuration file(s) and executes the complete
    pipeline or a specific step as specified.

    Execution options:
    - No options: Execute the complete pipeline
    - --step: Execute only a specific step
    - --etl: Execute a specific ETL (with multiple ETLs)
    - --name, -n: Custom run directory name
    - --overwrite, -o: Overwrite existing output directory
    - --log-file, -l: Save logs to file
    - --dry-run: Show the plan without executing
    - --json, -j: Output results as JSON instead of human-readable format
    - --verbose, -v: Increase verbosity (-v: INFO, -vv/-vvv: DEBUG)

    CONFIGS accepts one or more config names, comma-separated names, or paths.
    Short names resolve to config_dir/*.yaml. Absolute/relative paths are used as-is.
    Subdirectory paths (e.g. "v0/etl") resolve relative to config_dir.
    Wildcards are supported — quote them to prevent shell expansion:

    Examples:
        energizados run etl                            # Run config/etl.yaml
        energizados run etl,train                      # Merge and run both configs
        energizados run etl train                      # Same, space-separated
        energizados run v0/etl                         # Run config/v0/etl.yaml
        energizados run v0/etl v0/train                # Run from subdirectory
        energizados run 'v0/exp*'                      # Wildcard (quoted)
        energizados run eda                             # Run config/eda.yaml
        energizados run --config-path /custom etl       # Use /custom/etl.yaml
        energizados run /abs/path/custom.yaml            # Use absolute path directly
        energizados run etl -v                         # Run with INFO level logging
        energizados run etl -vv                        # Run with DEBUG level logging
        energizados run train -n my_experiment          # Run with custom run directory name
        energizados run train -o                       # Overwrite existing output
        energizados run train -l output/run.log        # Save logs to file
        energizados run train --json                   # Output results as JSON
    """
    # Configure logging (completely disable in JSON mode to avoid polluting JSON output)
    if not json:
        _setup_logging(verbose, log_file)

    # Validate run name if provided
    import re

    if name is not None:
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            raise click.BadParameter(
                "Run name can only contain letters, numbers, dashes and underscores"
            )

    from energizados.cli.compat import check_project_compatibility
    from energizados.cli.config_resolver import ConfigResolutionError, resolve_configs
    from energizados.cli.run import (
        execute_etl,
        execute_pipeline,
        execute_step,
        merge_configs,
    )
    from energizados.cli.ui import print_error, print_info, print_success
    from energizados.core.exceptions import StepValidationError

    try:
        # configs is a tuple from nargs=-1.
        # Support both "etl,train" (comma-sep in one arg) and "etl train" (space-sep, multiple args).
        # Flatten: split each token by comma, then join as a single comma-separated string for the resolver.
        tokens = [t.strip() for raw in configs for t in raw.split(",") if t.strip()]
        configs_str = ",".join(tokens)

        # Resolve config names to paths
        config_paths = resolve_configs(configs_str, config_path)

        # Check per-section schema compatibility before executing
        merged_for_check = merge_configs(config_paths)
        check_project_compatibility(merged_for_check)

        # If --etl is specified, execute specific ETLs
        if etl:
            if not json:
                print_info(f"Executing ETL '{etl}' (and its dependencies)...")
            result = execute_etl(config_paths, etl_name=etl, dry_run=dry_run)
            if json:
                _output_json(result)
            elif not dry_run:
                print_success("ETLs completed successfully")
            return

        # If --step is specified, execute only that step
        if step:
            if dry_run:
                if not json:
                    print_info(f"Dry-run mode for step '{step}'...")
                from energizados.cli.validate import validate_config

                result = validate_config(config_paths, verbose=verbose > 0)
                if json:
                    _output_json(result)
                return

            if not json:
                print_info(f"Executing step '{step}' of the pipeline...")
            result = execute_step(
                config_paths, step, run_name=name, overwrite=overwrite, profile_memory=verbose >= 2
            )
            if json:
                # Wrap result in RunResult for JSON output
                from energizados.api.run_state import RunResult

                _output_json(RunResult.from_context(result))
            else:
                print_success("Step completed successfully")
            return

        # If dry-run without step or etl, show ETLs plan if it exists
        if dry_run:
            if not json:
                print_info("Dry-run mode - showing execution plan...")
            from energizados.cli.run import show_etl_plan

            try:
                plan = show_etl_plan(config_paths)
                if json:
                    _output_json({"plan": plan})
                else:
                    click.echo(plan)
            except Exception:
                # No ETLs, show general validation
                from energizados.cli.validate import validate_config

                result = validate_config(config_paths, verbose=verbose > 0)
                if json:
                    _output_json(result)
            return

        # Execute complete pipeline.
        # Group configs into ordered execution runs that preserve the order
        # the user passed them. A step type appearing more than once (e.g.
        # train_01,train_02) runs once per config; otherwise consecutive
        # unique types coalesce into one merged pipeline.
        # Examples:
        #   etl,train              → one merged run [etl,train]
        #   train_01,train_02      → two runs [train_01],[train_02]
        #   etl,train_01,train_02  → [etl],[train_01],[train_02]
        #   etl*,train*,infer      → etls, then trains, then infer LAST
        from energizados.api.run_state import RunResult
        from energizados.cli.run import build_ordered_runs

        runs = build_ordered_runs(config_paths)

        if json:
            # For JSON output, collect all results in order
            all_results = []
            for run_paths in runs:
                result = execute_pipeline(
                    run_paths, run_name=name, overwrite=overwrite, profile_memory=verbose >= 2
                )
                all_results.append(RunResult.from_context(result).to_dict())

            # Output results as JSON
            if len(all_results) == 1:
                _output_json(all_results[0])
            else:
                _output_json({"runs": all_results})
        else:
            # Normal human-readable output — execute each run in order
            for run_paths in runs:
                execute_pipeline(
                    run_paths, run_name=name, overwrite=overwrite, profile_memory=verbose >= 2
                )

    except ConfigResolutionError as e:
        logger.error("Config resolution failed: %s", e)
        print_error(str(e))
        raise click.Abort()
    except FileNotFoundError as e:
        logger.error("Required file not found: %s", e)
        print_error(str(e))
        raise click.Abort()
    except StepValidationError as e:
        from rich.panel import Panel

        from energizados.cli.ui import console

        # Surface the failure through the logging system so it reaches run.log
        # (the FileHandler only sees logging records, not Rich console output).
        logger.error("Validation failed in step %s: %s", getattr(e, "step", "unknown"), e)
        console.print(
            Panel(
                str(e),
                title="[bold red]✗  Validation failed[/]",
                border_style="red",
                padding=(1, 2),
            )
        )
        raise click.Abort()
    except Exception as e:
        # Log with traceback so unexpected failures are diagnosable from run.log.
        logger.error("Pipeline execution failed: %s", e, exc_info=True)
        print_error(f"Error executing pipeline: {e}")
        if verbose:
            from energizados.cli.ui import console

            console.print_exception(show_locals=verbose > 1)
        else:
            print_info("Tip: Run 'energizados validate <config>' to check")
            print_info("      your configuration before running")
        raise click.Abort()


@cli.command()
@click.argument("configs", nargs=-1, required=True)
@click.option(
    "--config-path",
    "-p",
    default=None,
    help="Config directory (default: ./config/)",
)
@click.option(
    "--json",
    "-j",
    is_flag=True,
    default=False,
    help="Output results as JSON instead of human-readable format",
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase verbosity (-v: INFO, -vv/-vvv: DEBUG)",
)
@click.pass_context
def validate(ctx, configs, config_path, json, verbose):
    """
    Validate YAML configuration file(s).

    This command verifies that the configuration file(s) are valid
    and that all references to classes and parameters are correct.

    CONFIGS accepts one or more config names, comma-separated names, or paths.
    Short names resolve to config_dir/*.yaml. Absolute/relative paths are used as-is.
    Subdirectory paths (e.g. "v0/etl") resolve relative to config_dir.
    Wildcards are supported — quote them to prevent shell expansion.

    Examples:
        energizados validate etl                     # Validate config/etl.yaml
        energizados validate etl,train              # Validate both configs
        energizados validate etl train              # Same, space-separated
        energizados validate 'v0/exp*'              # Wildcard (quoted)
        energizados validate v0/etl                  # Validate config/v0/etl.yaml
        energizados validate eda                     # Validate config/eda.yaml
        energizados validate etl -v                 # Validate with INFO level logging
        energizados validate etl -vv                # Validate with DEBUG level logging
        energizados validate etl --json             # Output validation results as JSON
    """
    # Configure logging (completely disable in JSON mode to avoid polluting JSON output)
    if not json:
        _setup_logging(verbose)

    from energizados.cli.compat import check_project_compatibility
    from energizados.cli.config_resolver import ConfigResolutionError, resolve_configs
    from energizados.cli.run import merge_configs
    from energizados.cli.ui import print_error, print_info, print_success
    from energizados.cli.validate import validate_config

    try:
        tokens = [t.strip() for raw in configs for t in raw.split(",") if t.strip()]
        configs_str = ",".join(tokens)

        # Resolve config names to paths
        config_paths = resolve_configs(configs_str, config_path)

        # Check per-section schema compatibility before validating
        merged_for_check = merge_configs(config_paths)
        check_project_compatibility(merged_for_check)

        if not json:
            for resolved_path in config_paths:
                print_info(f"Validating: {resolved_path}")

        # Delegate to API validate_dict
        from energizados.api import validate_dict

        merged_config = merge_configs(config_paths)
        result = validate_dict(merged_config, "train")  # Use "train" as default type

        if json:
            _output_json(result)
        else:
            # Use existing validation output formatting
            # Call validate_config for its human output, but ignore errors since we already validated
            try:
                validate_config(config_paths, verbose=verbose > 0)
            except Exception:  # nosec B110
                # Already validated via API, ignore any errors from formatting
                pass
            print_success("Configuration is valid")
    except ConfigResolutionError as e:
        print_error(str(e))
        raise click.Abort()
    except FileNotFoundError as e:
        print_error(str(e))
        raise click.Abort()
    except Exception as e:
        print_error(f"Validation failed: {e}")
        print_info("Tip: Fix the configuration errors above and try again")
        raise click.Abort()


@cli.command()
@click.option(
    "--json",
    "-j",
    is_flag=True,
    default=False,
    help="Output results as JSON instead of human-readable format",
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase verbosity (-v: INFO, -vv/-vvv: DEBUG)",
)
@click.option(
    "--optional",
    "-o",
    is_flag=True,
    help="Include optional visualization packages (matplotlib, seaborn)",
)
@click.pass_context
def doctor(ctx, json, verbose, optional):
    """
    Check system information and validate environment.

    This command displays system information and validates that
    Python version and required packages meet the minimum
    requirements for Energizados.

    Examples:
        energizados doctor
        energizados doctor -v
        energizados doctor -vv
        energizados doctor --optional
        energizados doctor --json              # Output health checks as JSON
    """
    # Configure logging (completely disable in JSON mode to avoid polluting JSON output)
    if not json:
        _setup_logging(verbose)

    from energizados.cli.doctor import format_report
    from energizados.cli.ui import console, print_error, print_info

    try:
        if not json:
            print_info("Running environment diagnostics...")

        # Delegate to API doctor
        from energizados.api import doctor

        report = doctor(include_optional=optional)

        if json:
            _output_json(report)
        else:
            renderables = format_report(report, verbose=verbose)

            # Print each renderable directly via the singleton console
            for renderable in renderables:
                console.print(renderable)

            if not report.is_healthy():
                # Exit with error code but don't print extra message
                raise SystemExit(1)

    except click.Abort:
        # User aborted or intentional exit
        raise
    except SystemExit:
        # Forward the exit code
        raise
    except Exception as e:
        print_error(f"Error running diagnostics: {e}")
        raise click.Abort()


if __name__ == "__main__":
    cli()
