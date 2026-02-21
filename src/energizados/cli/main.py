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
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Forzar la creación eliminando el directorio existente si es necesario",
)
@click.pass_context
def init(ctx, project_name, template, path, copy_from, force):
    """
    Inicializar un nuevo proyecto Energizados.

    Este comando crea la estructura base de un proyecto con todos los
    archivos necesarios para personalizar el pipeline.

    PROJECT_NAME es el nombre del proyecto a crear.

    Ejemplos:
        energizados init mi_proyecto              # Crear desde template
        energizados init nuevo --copy existente   # Copiar desde proyecto existente
        energizados init mi_proyecto --force      # Reemplazar si existe
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
            force=force,
        )
        click.echo(f"\n✓ Proyecto creado exitosamente en: {project_path}")
        click.echo("\n📝 Próximos pasos:")
        click.echo(f"  1. cd {project_name}")
        click.echo("  2. Editar los archivos de configuración en config/:")
        click.echo("     - etls.yaml")
        click.echo("     - feature_pipeline.yaml")
        click.echo("     - training.yaml")
        click.echo("     - inference.yaml")
        click.echo("  3. (Opcional) Personalizar src/data/custom_etl.py")
        click.echo("  4. energizados run --config config/etls.yaml --config config/feature_pipeline.yaml --config config/training.yaml")
    except FileExistsError as e:
        # Preguntar si desea eliminar y recrear
        if click.confirm(f"\n{e}\n¿Deseas eliminar el directorio existente y recrearlo?", default=False):
            click.echo("🗑️  Eliminando directorio existente...")
            create_project(
                project_name=project_name,
                project_path=project_path,
                template=template,
                copy_from=copy_from,
                force=True,
            )
            click.echo(f"\n✓ Proyecto creado exitosamente en: {project_path}")
            click.echo("\n📝 Próximos pasos:")
            click.echo(f"  1. cd {project_name}")
            click.echo("  2. Editar los archivos de configuración en config/:")
            click.echo("     - etls.yaml")
            click.echo("     - feature_pipeline.yaml")
            click.echo("     - training.yaml")
            click.echo("     - inference.yaml")
            click.echo("  3. (Opcional) Personalizar src/data/custom_etl.py")
            click.echo("  4. energizados run --config config/etls.yaml --config config/feature_pipeline.yaml --config config/training.yaml")
        else:
            click.echo("\n✗ Operación cancelada.", err=True)
            raise click.Abort()
    except Exception as e:
        click.echo(f"\n✗ Error creando proyecto: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option(
    "--config",
    "-c",
    "config_paths",
    multiple=True,
    required=True,
    type=click.Path(exists=True),
    help="Ruta(s) al archivo(s) de configuración YAML. Puede usarse múltiples veces.",
)
@click.option(
    "--step",
    "-s",
    help="Ejecutar solo un paso específico del pipeline (etl, feature_pipeline, training, evaluation, inference)",
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
def run(ctx, config_paths, step, etl, dry_run):
    """
    Ejecutar un pipeline desde configuración YAML.

    Este comando lee el(los) archivo(s) de configuración y ejecuta el pipeline
    completo o un paso específico según lo especificado.

    Opciones de ejecución:
    - Sin opciones: Ejecuta el pipeline completo
    - --step: Ejecuta solo un paso específico
    - --etl: Ejecuta una ETL específica (con múltiples ETLs)
    - --dry-run: Muestra el plan sin ejecutar

    Se pueden especificar múltiples archivos de configuración:
        energizados run --config config/etls.yaml --config config/feature_pipeline.yaml --config config/training.yaml
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
            execute_etl(list(config_paths), etl_name=etl, dry_run=dry_run)
            if not dry_run:
                click.echo("\n✓ ETLs completadas exitosamente")
            return

        # Si se especifica --step, ejecuta solo ese paso
        if step:
            if dry_run:
                click.echo(f"🔍 Modo dry-run para paso '{step}'...")
                from energizados.cli.validate import validate_config

                validate_config(list(config_paths), verbose=True)
                return

            click.echo(f"⚡ Ejecutando paso '{step}' del pipeline...")
            execute_step(list(config_paths), step)
            click.echo("\n✓ Paso completado exitosamente")
            return

        # Si es dry-run sin step ni etl, mostrar plan de ETLs si existe
        if dry_run:
            from energizados.cli.run import show_etl_plan

            click.echo("🔍 Modo dry-run - mostrando plan de ejecución...")
            try:
                plan = show_etl_plan(list(config_paths))
                click.echo(plan)
            except Exception:
                # No hay ETLs, mostrar validación general
                from energizados.cli.validate import validate_config

                validate_config(list(config_paths), verbose=True)
            return

        # Ejecutar pipeline completo
        click.echo("⚡ Ejecutando pipeline completo...")
        execute_pipeline(list(config_paths))
        click.echo("\n✓ Pipeline completado exitosamente")

    except Exception as e:
        click.echo(f"\n✗ Error ejecutando pipeline: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option(
    "--config",
    "-c",
    "config_paths",
    multiple=True,
    required=True,
    type=click.Path(exists=True),
    help="Ruta(s) al archivo(s) de configuración YAML. Puede usarse múltiples veces.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Mostrar detalles completos de la validación",
)
@click.pass_context
def validate(ctx, config_paths, verbose):
    """
    Validar archivo(s) de configuración YAML.

    Este comando verifica que el(los) archivo(s) de configuración sea(n) válido(s)
    y que todas las referencias a clases y parámetros sean correctas.
    """
    from energizados.cli.validate import validate_config

    try:
        for config_path in config_paths:
            click.echo(f"🔍 Validando configuración: {config_path}")
        validate_config(list(config_paths), verbose=verbose)
        click.echo("\n✓ Configuración válida")
    except Exception as e:
        click.echo(f"\n✗ Validación falló: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()
