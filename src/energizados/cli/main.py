"""
Main CLI entry point for Energizados Framework.

This module defines the main command and the available subcommands.
"""

import logging
from pathlib import Path

import click


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

    project_path = Path(path) / project_name

    try:
        if copy_from:
            source_path = Path(path) / copy_from
            if not source_path.exists():
                click.echo(f"\n✗ Source project '{copy_from}' does not exist at: {source_path}", err=True)
                raise click.Abort()
            click.echo(f"📋 Copying project from '{copy_from}'...")
        else:
            click.echo(f"🚀 Creating project '{project_name}'...")

        create_project(
            project_name=project_name,
            project_path=project_path,
            template=template,
            copy_from=copy_from,
            force=force,
        )
        click.echo(f"\n✓ Project created successfully at: {project_path}")
        click.echo("\n📝 Next steps:")
        click.echo(f"  1. cd {project_name}")
        click.echo("  2. Edit the configuration files in config/:")
        click.echo("     - etls.yaml")
        click.echo("     - training.yaml")
        click.echo("     - inference.yaml")
        click.echo("  3. (Optional) Customize src/data/custom_etl.py")
        click.echo("  4. energizados run --config config/etls.yaml --config config/training.yaml")
    except FileExistsError as e:
        # Ask if they want to delete and recreate
        if click.confirm(f"\n{e}\nDo you want to delete the existing directory and recreate it?", default=False):
            click.echo("🗑️  Removing existing directory...")
            create_project(
                project_name=project_name,
                project_path=project_path,
                template=template,
                copy_from=copy_from,
                force=True,
            )
            click.echo(f"\n✓ Project created successfully at: {project_path}")
            click.echo("\n📝 Next steps:")
            click.echo(f"  1. cd {project_name}")
            click.echo("  2. Edit the configuration files in config/:")
            click.echo("     - etls.yaml")
            click.echo("     - training.yaml")
            click.echo("     - inference.yaml")
            click.echo("  3. (Optional) Customize src/data/custom_etl.py")
            click.echo("  4. energizados run --config config/etls.yaml --config config/training.yaml")
        else:
            click.echo("\n✗ Operation cancelled.", err=True)
            raise click.Abort()
    except Exception as e:
        click.echo(f"\n✗ Error creating project: {e}", err=True)
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

    try:
        # If --etl is specified, execute specific ETLs
        if etl:
            click.echo(f"⚡ Executing ETL '{etl}' (and its dependencies)...")
            execute_etl(list(config_paths), etl_name=etl, dry_run=dry_run)
            if not dry_run:
                click.echo("\n✓ ETLs completed successfully")
            return

        # If --step is specified, execute only that step
        if step:
            if dry_run:
                click.echo(f"🔍 Dry-run mode for step '{step}'...")
                from energizados.cli.validate import validate_config

                validate_config(list(config_paths), verbose=True)
                return

            click.echo(f"⚡ Executing step '{step}' of the pipeline...")
            execute_step(list(config_paths), step)
            click.echo("\n✓ Step completed successfully")
            return

        # If dry-run without step or etl, show ETLs plan if it exists
        if dry_run:
            from energizados.cli.run import show_etl_plan

            click.echo("🔍 Dry-run mode - showing execution plan...")
            try:
                plan = show_etl_plan(list(config_paths))
                click.echo(plan)
            except Exception:
                # No ETLs, show general validation
                from energizados.cli.validate import validate_config

                validate_config(list(config_paths), verbose=True)
            return

        # Execute complete pipeline
        click.echo("⚡ Executing complete pipeline...")
        execute_pipeline(list(config_paths))
        click.echo("\n✓ Pipeline completed successfully")

    except Exception as e:
        click.echo(f"\n✗ Error executing pipeline: {e}", err=True)
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
    from energizados.cli.validate import validate_config

    try:
        for config_path in config_paths:
            click.echo(f"🔍 Validating configuration: {config_path}")
        validate_config(list(config_paths), verbose=verbose)
        click.echo("\n✓ Configuration is valid")
    except Exception as e:
        click.echo(f"\n✗ Validation failed: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()
