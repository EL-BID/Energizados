"""
Main CLI entry point for Energizados Framework.

This module defines main command and available subcommands.
"""

import logging
from pathlib import Path

import click
from rich.panel import Panel
from rich.tree import Tree


def _setup_logging(verbose: int = 0):
    """
    Configures logging for the CLI.

    Args:
        verbose: Verbosity level (0=WARNING, 1=INFO, 2+=DEBUG)
    """
    if verbose == 0:
        level = logging.WARNING
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    # Configure console handler
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(message)s"))

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = []  # Remove existing handlers
    root_logger.addHandler(handler)


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
    edit_config.add("[cyan]•[/] etls.yaml")
    edit_config.add("[cyan]•[/] training.yaml")
    edit_config.add("[cyan]•[/] inference.yaml")
    edit_config.add("[cyan]•[/] eda.yaml")
    tree.add("[cyan]3.[/] (Optional) Customize src/data/custom_etl.py")
    tree.add("[cyan]4.[/] energizados eda --config config/eda.yaml")
    tree.add("[cyan]5.[/] energizados run --config config/etls.yaml --config config/training.yaml")

    panel = Panel(tree, title="[bold]Next Steps[/]", border_style="cyan")
    console.print("\n")
    console.print(panel)
    console.print()


@click.group()
@click.version_option(version="1.0.0", prog_name="energizados")
@click.option("--verbose", "-v", count=True, help="Increase verbosity (-v, -vv, -vvv)")
@click.pass_context
def cli(ctx, verbose):
    """
    Energizados - Framework for detecting fraud in energy consumption.

    This framework allows creating ML pipelines for fraud detection
    with simple configuration and extensibility.

    Available commands:
    - init: Initialize a new project
    - run: Execute a pipeline from configuration
    - validate: Validate configuration file
    - eda: Run Exploratory Data Analysis on a dataset
    - doctor: Check system information and validate environment

    Verbosity options:
        -v: INFO (shows informative messages)
        -vv: DEBUG (shows debug messages)
        -vvv: DEBUG (same as -vv)

    For help on a specific command:
        energizados <command> --help
    """
    # Configure logging
    _setup_logging(verbose)

    # Shared context between commands
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


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
@click.pass_context
def init(ctx, project_name, template, path, copy_from, force):
    """
    Initialize a new Energizados project.

    This command creates the base structure of a project with all the
    necessary files to customize the pipeline.

    PROJECT_NAME is the name of the project to create.

    Examples:
        energizados init my_project              # Create from template
        energizados init new --copy existing     # Copy from existing project
        energizados init my_project --force      # Replace if exists
    """
    from energizados.cli.init import create_project
    from energizados.cli.ui import print_error, print_info, print_success

    project_path = Path(path) / project_name

    try:
        if copy_from:
            source_path = Path(path) / copy_from
            if not source_path.exists():
                print_error(f"Source project '{copy_from}' does not exist at: {source_path}")
                raise click.Abort()
            print_info(f"Copying project from '{copy_from}'...")
        else:
            print_info(f"Creating project '{project_name}'...")

        create_project(
            project_name=project_name,
            project_path=project_path,
            template=template,
            copy_from=copy_from,
            force=force,
        )
        print_success(f"Project created successfully at: {project_path}")
        _print_next_steps(project_name)
    except FileExistsError as e:
        # Ask if they want to delete and recreate
        if click.confirm(
            f"\n{e}\nDo you want to delete the existing directory and recreate it?", default=False
        ):
            print_info("Removing existing directory...")
            create_project(
                project_name=project_name,
                project_path=project_path,
                template=template,
                copy_from=copy_from,
                force=True,
            )
            print_success(f"Project created successfully at: {project_path}")
            _print_next_steps(project_name)
        else:
            print_error("Operation cancelled.")
            raise click.Abort()
    except Exception as e:
        print_error(f"Error creating project: {e}")
        print_info("Tip: Check the project name and try again")
        raise click.Abort()


@cli.command()
@click.option(
    "--config",
    "-c",
    "config_paths",
    multiple=True,
    required=True,
    type=click.Path(exists=True),
    help="Path(s) to YAML configuration file(s). Can be used multiple times.",
)
@click.option(
    "--step",
    "-s",
    help="Run only a specific pipeline step (etl, split, training, evaluation, inference)",
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
@click.pass_context
def run(ctx, config_paths, step, etl, dry_run):
    """
    Execute a pipeline from YAML configuration.

    This command reads the configuration file(s) and executes the complete
    pipeline or a specific step as specified.

    Execution options:
    - No options: Execute the complete pipeline
    - --step: Execute only a specific step
    - --etl: Execute a specific ETL (with multiple ETLs)
    - --dry-run: Show the plan without executing

    You can specify multiple configuration files:
        energizados run --config config/etls.yaml --config config/training.yaml
    """
    from energizados.cli.run import (
        execute_etl,
        execute_pipeline,
        execute_step,
    )
    from energizados.cli.ui import print_error, print_info, print_success

    try:
        # If --etl is specified, execute specific ETLs
        if etl:
            print_info(f"Executing ETL '{etl}' (and its dependencies)...")
            execute_etl(list(config_paths), etl_name=etl, dry_run=dry_run)
            if not dry_run:
                print_success("ETLs completed successfully")
            return

        # If --step is specified, execute only that step
        if step:
            if dry_run:
                print_info(f"Dry-run mode for step '{step}'...")
                from energizados.cli.validate import validate_config

                validate_config(list(config_paths), verbose=True)
                return

            print_info(f"Executing step '{step}' of the pipeline...")
            execute_step(list(config_paths), step)
            print_success("Step completed successfully")
            return

        # If dry-run without step or etl, show ETLs plan if it exists
        if dry_run:
            from energizados.cli.run import show_etl_plan

            print_info("Dry-run mode - showing execution plan...")
            try:
                plan = show_etl_plan(list(config_paths))
                click.echo(plan)
            except Exception:
                # No ETLs, show general validation
                from energizados.cli.validate import validate_config

                validate_config(list(config_paths), verbose=True)
            return

        # Execute complete pipeline
        print_info("Executing complete pipeline...")
        execute_pipeline(list(config_paths))
        print_success("Pipeline completed successfully")

    except Exception as e:
        print_error(f"Error executing pipeline: {e}")
        print_info("Tip: Run 'energizados validate --config <file>' to check")
        print_info("      your configuration before running")
        raise click.Abort()


@cli.command()
@click.option(
    "--config",
    "-c",
    "config_paths",
    multiple=True,
    required=True,
    type=click.Path(exists=True),
    help="Path(s) to YAML configuration file(s). Can be used multiple times.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show complete validation details",
)
@click.pass_context
def validate(ctx, config_paths, verbose):
    """
    Validate YAML configuration file(s).

    This command verifies that the configuration file(s) are valid
    and that all references to classes and parameters are correct.
    """
    from energizados.cli.ui import print_error, print_info, print_success
    from energizados.cli.validate import validate_config

    try:
        for config_path in config_paths:
            print_info(f"Validating: {config_path}")
        validate_config(list(config_paths), verbose=verbose)
        print_success("Configuration is valid")
    except Exception as e:
        print_error(f"Validation failed: {e}")
        print_info("Tip: Fix the configuration errors above and try again")
        raise click.Abort()


@cli.command()
@click.option(
    "--input",
    "-i",
    "input_path",
    default=None,
    help="Path to input dataset (parquet or CSV). Overrides config file.",
)
@click.option(
    "--target",
    "-t",
    "target_column",
    default=None,
    help="Name of binary target column.",
)
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to eda.yaml configuration file.",
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    default=None,
    help="Output directory for EDA report and plots.",
)
@click.option(
    "--lat-col",
    "lat_col",
    default=None,
    help="Name of latitude column (enables geospatial analysis).",
)
@click.option(
    "--lon-col",
    "lon_col",
    default=None,
    help="Name of longitude column (enables geospatial analysis).",
)
@click.option(
    "--etl",
    "-e",
    "etl_name",
    default=None,
    help="Name of an ETL defined in etls.yaml whose output to analyze.",
)
@click.option(
    "--skip-sections",
    "skip_sections",
    default=None,
    help="Comma-separated list of sections to skip (e.g. 'geo,join,segmentation').",
)
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Show configuration that would be used without running the analysis.",
)
@click.pass_context
def eda(
    ctx,
    input_path,
    target_column,
    config_path,
    output_dir,
    lat_col,
    lon_col,
    etl_name,
    skip_sections,
    dry_run,
):
    """
    Run Exploratory Data Analysis (EDA) on a dataset.

    Analyzes data quality, column distributions, target variable and
    feature predictive power. Generates a self-contained HTML report.

    Examples:

        energizados eda --input data/raw/dataset.parquet --target target

        energizados eda --config config/eda.yaml

        energizados eda --config config/eda.yaml --etl sample

        energizados eda --config config/eda.yaml --lat-col LATITUDE --lon-col LONGITUDE

        energizados eda --config config/eda.yaml --skip-sections "geo,join"

        energizados eda --config config/eda.yaml --dry-run
    """
    import yaml

    # Load config if provided
    config = {}
    if config_path:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            from energizados.cli.ui import print_error

            print_error(f"Error reading configuration: {e}")
            raise click.Abort()

    # CLI args override config
    eda_cfg = config.get("eda", config)

    # Apply skip-sections overrides
    if skip_sections:
        skipped = [s.strip() for s in skip_sections.split(",")]
        sections = eda_cfg.setdefault("sections", {})
        for section in skipped:
            sections.setdefault(section, {})["enabled"] = False

    # Apply lat/lon CLI overrides to column_detection
    if lat_col or lon_col:
        col_det = eda_cfg.setdefault("column_detection", {})
        if lat_col:
            col_det["lat_col"] = lat_col
        if lon_col:
            col_det["lon_col"] = lon_col
        # Auto-enable geospatial section when coordinates are provided via CLI
        eda_cfg.setdefault("sections", {}).setdefault("geospatial", {}).setdefault("enabled", True)

    # Resolve input path: --etl takes precedence, then --input, then config
    resolved_input = input_path
    if not resolved_input and etl_name:
        # Resolve ETL output from etls.yaml (config may be an etls.yaml)
        etls_cfg = config.get("etls", {})
        etl_entry = etls_cfg.get(etl_name, {})
        resolved_input = etl_entry.get("output")
        if not resolved_input:
            from energizados.cli.ui import print_error, print_step

            print_error(
                f"ETL '{etl_name}' not found or has no 'output' defined in the configuration."
            )
            raise click.Abort()

        print_step(f"Usando output del ETL '{etl_name}': {resolved_input}")

    if not resolved_input:
        data_sources = eda_cfg.get("data_sources", {})
        primary = data_sources.get("primary", {})
        resolved_input = primary.get("path")

    if not resolved_input:
        from energizados.cli.ui import print_error

        print_error("Se requiere --input, --etl, o config/eda.yaml con data_sources.primary.path")
        raise click.Abort()

    # Resolve output dir
    resolved_output = output_dir
    if not resolved_output:
        output_cfg = eda_cfg.get("output", {})
        resolved_output = output_cfg.get("output_dir", "output/eda/")

    # Resolve target
    resolved_target = target_column
    if not resolved_target:
        data_sources = eda_cfg.get("data_sources", {})
        resolved_target = data_sources.get("primary", {}).get("target_col")

    if dry_run:
        from energizados.cli.ui import console

        console.print("[dim]Modo dry-run - configuración que se usaría:[/]")
        console.print(f"[dim]  Entrada:  {resolved_input}[/]")
        console.print(f"[dim]  Target:   {resolved_target or '(no especificado)'}[/]")
        console.print(f"[dim]  Salida:   {resolved_output}[/]")
        if etl_name:
            console.print(f"[dim]  ETL:      {etl_name}[/]")
        if lat_col or lon_col:
            console.print(f"[dim]  Coordenadas: lat={lat_col}, lon={lon_col}[/]")
        if skip_sections:
            console.print(f"[dim]  Secciones omitidas: {skip_sections}[/]")
        return

    try:
        from energizados.eda.dataset_explorer import DatasetExplorer

        col_detection = eda_cfg.get("column_detection", {})

        explorer = DatasetExplorer(
            input_path=resolved_input,
            target_column=resolved_target,
            id_column=col_detection.get("id_col"),
            date_column=col_detection.get("date_col"),
            lat_column=col_detection.get("lat_col"),
            lon_column=col_detection.get("lon_col"),
            zone_column=col_detection.get("zone_col"),
            periods_suffix=col_detection.get("periods_suffix", "_anterior"),
            output_dir=resolved_output,
            sections=eda_cfg.get("sections"),
            config=config if config else None,
        )

        results = explorer.run()
        report_path = results.get("report_path", "")
        alert_count = len(results.get("alerts", []))
        error_count = sum(1 for a in results.get("alerts", []) if a.get("severity") == "ERROR")
        warning_count = sum(1 for a in results.get("alerts", []) if a.get("severity") == "WARNING")

        from energizados.cli.ui import console, print_error, print_success

        print_success("EDA completado exitosamente")
        console.print(f"  Reporte: {report_path}")
        console.print(
            f"  Alertas: {alert_count} total ({error_count} errores, {warning_count} advertencias)"
        )

    except FileNotFoundError as e:
        from energizados.cli.ui import print_error

        print_error(f"File not found: {e}")
        raise click.Abort()
    except Exception as e:
        from energizados.cli.ui import print_error, print_info

        print_error(f"Error executing EDA: {e}")
        print_info("Tip: Run 'energizados validate --config <file>' to verify your configuration")
        raise click.Abort()


@cli.command()
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed system information",
)
@click.option(
    "--optional",
    "-o",
    is_flag=True,
    help="Include optional visualization packages (matplotlib, seaborn)",
)
@click.pass_context
def doctor(ctx, verbose, optional):
    """
    Check system information and validate environment.

    This command displays system information and validates that
    Python version and required packages meet the minimum
    requirements for Energizados.

    Examples:
        energizados doctor
        energizados doctor --verbose
        energizados doctor --optional
    """
    from energizados.cli.doctor import format_report, run_checks
    from energizados.cli.ui import console, print_error, print_info

    try:
        print_info("Running environment diagnostics...")

        report = run_checks(include_optional=optional)
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
