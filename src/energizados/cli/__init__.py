"""Energizados Framework CLI module.

This module provides the command-line interface for the Energizados
framework, enabling users to initialize projects, run pipelines,
and validate configurations.

The CLI is built using Click and exposes the following main commands:
- init: Initialize a new project with templates
- run: Execute pipelines from YAML configuration
- validate: Validate configuration files

Example:
    To use the CLI programmatically:

    >>> from energizados.cli import cli
    >>> cli(['--help'])
"""

__all__ = ["cli"]
