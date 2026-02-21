"""
Main CLI entry point for Energizados Framework.

Este módulo define el comando principal y los subcomandos disponibles.
"""

from pathlib import Path

import click


@click.group()
@click.version_option(version="1.0.0", prog_name="energizados")
@click.pass_context
def cli(ctx):
    """
    Energizados - Framework para detección de fraude en consumo energético.

    Este framework permite crear pipelines de ML para detección de fraude
    con configuración simple y posibilidad de extensión.

    Comandos disponibles:
    - init: Inicializar un nuevo proyecto
    - run: Ejecutar un pipeline desde configuración
    - validate: Validar archivo de configuración

    Para ayuda sobre un comando específico:
        energizados <comando> --help
    """
    # Contexto compartido entre comandos
    ctx.ensure_object(dict)


@cli.command()
@click.argument("project_name")
@click.option(
    "--template",
    "-t",
    default="default",
    help="Template a usar para el proyecto (default)",
    show_default=True,
)
@click.option(
    "--path",
    "-p",
    default=".",
    help="Directorio donde crear el proyecto",
    show_default=True,
)
@click.option(
    "--copy",
    "-c",
    "copy_from",
    default=None,
    help="Copiar desde proyecto existente (tiene prioridad sobre --template)",
)
@click.pass_context
def init(ctx, project_name, template, path, copy_from):
    """
    Inicializar un nuevo proyecto Energizados.

    Este comando crea la estructura base de un proyecto con todos los
    archivos necesarios para personalizar el pipeline.

    PROJECT_NAME es el nombre del proyecto a crear.

    Ejemplos:
        energizados init mi_proyecto              # Crear desde template
        energizados init nuevo --copy existente   # Copiar desde proyecto existente
    """
    from energizados.cli.init import create_project

    project_path = Path(path) / project_name

    try:
        if copy_from:
            source_path = Path(path) / copy_from
            if not source_path.exists():
                click.echo(f"\n✗ El proyecto origen '{copy_from}' no existe en: {source_path}", err=True)
                raise click.Abort()
            click.echo(f"📋 Copiando proyecto desde '{copy_from}'...")
        else:
            click.echo(f"🚀 Creando proyecto '{project_name}'...")

        create_project(
            project_name=project_name,
            project_path=project_path,
            template=template,
            copy_from=copy_from,
        )
        click.echo(f"\n✓ Proyecto creado exitosamente en: {project_path}")
        click.echo("\n📝 Próximos pasos:")
        click.echo(f"  1. cd {project_name}")
        click.echo("  2. Editar configs/pipeline.yaml según tus necesidades")
        click.echo("  3. (Opcional) Personalizar etl/custom_etl.py")
        click.echo("  4. energizados run --config configs/pipeline.yaml")
    except Exception as e:
        click.echo(f"\n✗ Error creando proyecto: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option(
    "--config",
    "-c",
    "config_path",
    required=True,
    type=click.Path(exists=True),
    help="Ruta al archivo de configuración YAML",
)
@click.option(
    "--step",
    "-s",
    help="Ejecutar solo un paso específico del pipeline (etl, preprocessing, feature_selection, training, evaluation, inference)",
)
@click.option(
    "--etl",
    "-e",
    help="Ejecutar una ETL específica (y sus dependencias). Solo válido con múltiples ETLs.",
)
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Mostrar qué se ejecutaría sin ejecutar realmente (para ETLs muestra el plan de ejecución)",
)
@click.pass_context
def run(ctx, config_path, step, etl, dry_run):
    """
    Ejecutar un pipeline desde configuración YAML.

    Este comando lee el archivo de configuración y ejecuta el pipeline
    completo o un paso específico según lo especificado.

    Opciones de ejecución:
    - Sin opciones: Ejecuta el pipeline completo
    - --step: Ejecuta solo un paso específico
    - --etl: Ejecuta una ETL específica (con múltiples ETLs)
    - --dry-run: Muestra el plan sin ejecutar
    """
    from energizados.cli.run import (
        execute_etl,
        execute_pipeline,
        execute_step,
    )

    try:
        # Si se especifica --etl, ejecuta ETLs específicas
        if etl:
            click.echo(f"⚡ Ejecutando ETL '{etl}' (y sus dependencias)...")
            execute_etl(config_path, etl_name=etl, dry_run=dry_run)
            if not dry_run:
                click.echo("\n✓ ETLs completadas exitosamente")
            return

        # Si se especifica --step, ejecuta solo ese paso
        if step:
            if dry_run:
                click.echo(f"🔍 Modo dry-run para paso '{step}'...")
                from energizados.cli.validate import validate_config

                validate_config(config_path, verbose=True)
                return

            click.echo(f"⚡ Ejecutando paso '{step}' del pipeline...")
            execute_step(config_path, step)
            click.echo("\n✓ Paso completado exitosamente")
            return

        # Si es dry-run sin step ni etl, mostrar plan de ETLs si existe
        if dry_run:
            from energizados.cli.run import show_etl_plan

            click.echo("🔍 Modo dry-run - mostrando plan de ejecución...")
            try:
                plan = show_etl_plan(config_path)
                click.echo(plan)
            except Exception:
                # No hay ETLs, mostrar validación general
                from energizados.cli.validate import validate_config

                validate_config(config_path, verbose=True)
            return

        # Ejecutar pipeline completo
        click.echo("⚡ Ejecutando pipeline completo...")
        execute_pipeline(config_path)
        click.echo("\n✓ Pipeline completado exitosamente")

    except Exception as e:
        click.echo(f"\n✗ Error ejecutando pipeline: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option(
    "--config",
    "-c",
    "config_path",
    required=True,
    type=click.Path(exists=True),
    help="Ruta al archivo de configuración YAML",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Mostrar detalles completos de la validación",
)
@click.pass_context
def validate(ctx, config_path, verbose):
    """
    Validar archivo de configuración YAML.

    Este comando verifica que el archivo de configuración sea válido
    y que todas las referencias a clases y parámetros sean correctas.
    """
    from energizados.cli.validate import validate_config

    try:
        click.echo(f"🔍 Validando configuración: {config_path}")
        validate_config(config_path, verbose=verbose)
        click.echo("\n✓ Configuración válida")
    except Exception as e:
        click.echo(f"\n✗ Validación falló: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()
