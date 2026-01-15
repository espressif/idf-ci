# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import inspect
import typing as t
from pathlib import Path

import click
from pydantic import BaseModel
from tomlkit import TOMLDocument, load
from tomlkit import dumps as toml_dumps

from idf_ci.settings import CiSettings, get_ci_settings, pick_toml_file


def _parse_config_key(config_key: str) -> t.List[str]:
    """Parse a dot-separated path into a list of parts."""
    parts = [p.strip() for p in config_key.split('.') if p.strip()]
    if not parts:
        raise click.BadParameter('Empty path')
    return parts


def _iter_config_key_paths(data: t.Mapping[str, t.Any], prefix: str = '') -> t.Iterable[str]:
    for key in sorted(data.keys()):
        path = f'{prefix}.{key}' if prefix else key
        yield path
        value = data[key]
        if isinstance(value, dict):
            yield from _iter_config_key_paths(value, path)


def _complete_config_key(ctx, param, incomplete: str) -> t.List[str]:  # noqa: ARG001
    settings = get_ci_settings()
    data = settings.model_dump(mode='python', exclude_none=True)
    keys = _iter_config_key_paths(data)
    return [key for key in keys if key.startswith(incomplete)]


def _format_type(annotation: t.Any) -> str:
    origin = t.get_origin(annotation)
    if origin is None:
        if isinstance(annotation, type):
            return annotation.__name__
        return repr(annotation)

    if origin is t.Literal:
        return f'Literal[{", ".join(repr(a) for a in t.get_args(annotation))}]'

    if origin is t.Union:
        return f'Union[{", ".join(_format_type(a) for a in t.get_args(annotation))}]'

    return f'{origin.__name__}[{", ".join(_format_type(a) for a in t.get_args(annotation))}]'


def _get_model_class(annotation: t.Any) -> t.Optional[t.Type[BaseModel]]:
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return annotation

    origin = t.get_origin(annotation)
    if origin is t.Union:
        for arg in t.get_args(annotation):
            if inspect.isclass(arg) and issubclass(arg, BaseModel):
                return arg

    return None


def _resolve_field(config_key: str) -> t.Tuple[t.Optional[t.Type[BaseModel]], t.Any, str, t.Type[BaseModel]]:
    """Resolve a config key path to find the field and its containing class."""
    parts = _parse_config_key(config_key)

    current_cls: t.Optional[t.Type[BaseModel]] = CiSettings
    parent_cls: t.Type[BaseModel] = CiSettings
    field = None
    for part in parts:
        if current_cls is None:
            raise click.BadParameter(f'Config key is not a section: {".".join(parts)}')
        if part not in current_cls.model_fields:
            raise click.BadParameter(f'Unknown config key: {config_key}')
        parent_cls = current_cls
        field = current_cls.model_fields[part]
        current_cls = _get_model_class(field.annotation)

    return current_cls, field, parts[-1], parent_cls


def argument_config_key(func):
    return click.argument('config_key', shell_complete=_complete_config_key)(func)


@click.group()
def config():
    """Inspect and manage idf-ci configuration."""
    pass


@config.command()
@argument_config_key
def show(config_key: str):
    """Show the effective configuration after all overrides are applied."""
    settings = get_ci_settings()
    data = settings.model_dump(mode='python', exclude_none=True)
    config_path = _get_config_file_path()
    config_label = str(config_path) if config_path else '<not found>'
    config_data: t.Optional[TOMLDocument] = None
    if config_path:
        with open(config_path) as f:
            config_data = load(f)

    value = _get_value_by_config_key(data, config_key)
    # Determine value source
    if (
        CiSettings.CLI_OVERRIDES
        and _get_value_by_config_key(CiSettings.CLI_OVERRIDES, config_key, safe=True) is not None
    ):
        source = 'cli_override'
    elif config_data and _get_value_by_config_key(config_data, config_key, safe=True) is not None:
        source = 'config_file'
    else:
        source = 'default'

    # Show config file location
    click.echo(f'Config file: {config_label}')

    # Show value source
    if source == 'cli_override':
        click.echo('Source: CLI override (--config option)')
    elif source == 'config_file':
        click.echo(f'Source: Config file ({config_label})')
    else:
        click.echo('Source: Default value')

    click.echo()
    click.echo(_format_toml_value(config_key, value))


@config.command()
@argument_config_key
def explain(config_key: str):
    """Explain a config key, including type, default, and description."""
    next_cls, field, _, _ = _resolve_field(config_key)

    click.echo(f'Key: {config_key}')
    click.echo(f'Type: {_format_type(field.annotation)}')
    if field.description:
        click.echo(f'Description: {field.description}')

    if next_cls is not None and issubclass(next_cls, BaseModel):
        subkeys = sorted(next_cls.model_fields.keys())
        if subkeys:
            click.echo('Subkeys:')
            for key in subkeys:
                click.echo(f'  - {config_key}.{key}')
    else:
        if field.is_required():
            click.echo('Default: <required>')
        else:
            click.echo('Default (toml):')
            click.echo('```toml')
            click.echo(_format_toml_value(config_key, field.default))
            click.echo('```')

    origin = t.get_origin(field.annotation)
    if origin is t.Literal:
        values = ', '.join(repr(v) for v in t.get_args(field.annotation))
        click.echo(f'Choices: {values}')


def _get_value_by_config_key(data: t.Dict[str, t.Any], config_key: str, *, safe: bool = False) -> t.Any:
    """Navigate nested dict using dot-separated config key path.

    :param data: The dictionary to navigate
    :param config_key: Dot-separated path to the value
    :param safe: If True, return None on error instead of raising exceptions

    :returns: The value at the path, or None if safe=True and path is invalid
    """
    parts = _parse_config_key(config_key)
    cursor: t.Any = data
    for part in parts:
        if not isinstance(cursor, dict) or part not in cursor:
            if safe:
                return None
            raise click.BadParameter(f'Unknown config key: {config_key}')
        cursor = cursor[part]
    return cursor


def _get_config_file_path() -> t.Optional[Path]:
    """Get the path to the config file being used."""
    return pick_toml_file(CiSettings.CONFIG_FILE_PATH)


def _format_toml_value(path: str, value: t.Any) -> str:
    """Format a value as TOML syntax with proper nesting for the given path."""
    parts = _parse_config_key(path)

    if isinstance(value, str):
        # Use TOML multiline string format if the value contains newlines
        # This preserves newlines for CLI readability while being TOML-valid
        if '\n' in value or '\r' in value:
            # Escape triple quotes and backslashes for multiline strings
            escaped = value.replace('\\', '\\\\').replace('"""', '\\"""')
            return f'{path} = """\n{escaped}\n"""'
        # For single-line strings, escape special characters
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'{path} = "{escaped}"'

    # For complex values, build nested structure and let toml_dumps handle formatting
    data: t.Dict[str, t.Any] = {}
    cursor = data
    for part in parts[:-1]:
        cursor[part] = {}
        cursor = cursor[part]
    cursor[parts[-1]] = value
    return toml_dumps(data).strip()
