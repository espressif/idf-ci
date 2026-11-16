# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
"""Support for the ``disable_test`` pytest marker.

The marker disables a test case by an `esp-bool-parser
<https://github.com/espressif/esp-bool-parser>`__ expression, by targets, by sdkconfig
names, or by any combination of them:

.. code-block:: python

    @pytest.mark.disable_test(
        'IDF_TARGET == "esp32" and IDF_VERSION_MAJOR < 6',
        configs=['iram'],
        reason='IDF-1234, will fix it ASAP',
    )
    def test_foo(dut):
        pass

The positional argument is the boolean expression. All keyword arguments (``targets``,
``configs``, ``reason``) are optional, but at least one of the expression, ``targets``
or ``configs`` must be given. All the given conditions must match for the test case to
be disabled.

Only the closest marker is taken into account, so a marker on a test function overrides
the ones declared on its class or module.

``targets`` and ``configs`` entries that contain a comma are multi-DUT selectors,
matched against the whole test case. ``*`` matches any single DUT:

.. code-block:: python

    # disables every test case that runs on esp32p4, no matter how many DUTs
    @pytest.mark.disable_test(targets=['esp32p4'], reason='IDF-1234')
    def test_any_dut(dut):
        pass


    # disables only the two-DUT cases whose second DUT is esp32p4
    @pytest.mark.disable_test(targets=['*,esp32p4'], reason='IDF-1234')
    def test_two_duts(dut):
        pass
"""

import logging
import typing as t

import pytest
from esp_bool_parser import parse_bool_expr
from pydantic import BaseModel, ConfigDict, ValidationError, ValidationInfo, field_validator, model_validator

logger = logging.getLogger(__name__)


class DisableTestError(Exception):
    """Raised when a ``disable_test`` expression cannot be evaluated."""


def _normalize_selectors(key: str, value: t.Any) -> t.Tuple[t.Tuple[str, ...], ...]:
    """Normalize a ``targets``/``configs`` keyword argument.

    Each entry is split on commas, so a plain value becomes a one-element selector and
    ``'esp32,*'`` becomes a two-element one.

    :param key: Keyword argument name, used in the error message
    :param value: Value given by the user

    :returns: Tuple of selectors, each a tuple of non-empty strings

    :raises ValueError: If the value is not a string or a non-empty sequence of
        non-empty strings
    """
    if isinstance(value, str):
        values: t.Tuple[t.Any, ...] = (value,)
    elif isinstance(value, (list, tuple, set, frozenset)):
        values = tuple(value)
    else:
        raise ValueError(f'`{key}` must be a string or a list of strings, got {value!r}')

    if not values or any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError(f'`{key}` must be a string or a non-empty list of non-empty strings, got {value!r}')

    selectors = []
    for v in values:
        parts = tuple(part.strip() for part in v.split(','))
        if any(not part for part in parts):
            raise ValueError(f'`{key}` selector {v!r} contains an empty value')
        selectors.append(parts)

    return tuple(selectors)


def _selectors_match(selectors: t.Optional[t.Tuple[t.Tuple[str, ...], ...]], values: t.Sequence[str]) -> bool:
    """Check whether any selector matches the values of a test case.

    A one-element selector matches when any DUT has that value. A multi-element selector
    must have the same length as ``values`` and match it element-wise, where ``*``
    matches anything.

    :param selectors: Selectors to check, or None to match everything
    :param values: Per-DUT values of the test case

    :returns: True if any selector matches
    """
    if selectors is None:
        return True

    for selector in selectors:
        if len(selector) == 1:
            if selector[0] == '*' or selector[0] in values:
                return True
        elif len(selector) == len(values) and all(
            part == '*' or part == value for part, value in zip(selector, values)
        ):
            return True

    return False


class DisableTestRule(BaseModel):
    """Disable test rule parsed from a `disable_test` marker."""

    model_config = ConfigDict(extra='forbid', frozen=True)

    _ALLOWED_KWARGS: t.ClassVar[t.Tuple[str, ...]] = ('targets', 'configs', 'reason')

    expression: t.Optional[str] = None
    targets: t.Optional[t.Tuple[t.Tuple[str, ...], ...]] = None
    configs: t.Optional[t.Tuple[t.Tuple[str, ...], ...]] = None
    reason: str = ''

    @model_validator(mode='before')
    @classmethod
    def _unpack_marker(cls, data: t.Any) -> t.Any:
        """Accept a ``disable_test`` ``pytest.Mark`` as the input of ``model_validate``.

        :param data: A ``pytest.Mark``, or the usual mapping of field values

        :returns: Mapping of field values
        """
        if not isinstance(data, pytest.Mark):
            return data

        if len(data.args) > 1:
            raise ValueError(
                f'accepts at most one positional argument (the expression), got {len(data.args)}. '
                f'Use keyword arguments for {", ".join(cls._ALLOWED_KWARGS)}'
            )

        unknown_kwargs = sorted(set(data.kwargs) - set(cls._ALLOWED_KWARGS))
        if unknown_kwargs:
            raise ValueError(
                f'unknown keyword argument(s): {", ".join(unknown_kwargs)}. Supported: {", ".join(cls._ALLOWED_KWARGS)}'
            )

        kwargs: t.Dict[str, t.Any] = dict(data.kwargs)
        if data.args:
            kwargs['expression'] = data.args[0]

        return kwargs

    @field_validator('expression', mode='before')
    @classmethod
    def _validate_expression(cls, v: t.Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f'the expression must be a non-empty string, got {v!r}')
        return v.strip()

    @field_validator('targets', 'configs', mode='before')
    @classmethod
    def _validate_selectors(cls, v: t.Any, info: ValidationInfo) -> t.Tuple[t.Tuple[str, ...], ...]:
        return _normalize_selectors(info.field_name or '', v)

    @field_validator('reason', mode='before')
    @classmethod
    def _validate_reason(cls, v: t.Any) -> str:
        if v is None:
            return ''
        if not isinstance(v, str):
            raise ValueError(f'`reason` must be a string, got {v!r}')
        return v.strip()

    @model_validator(mode='after')
    def _validate_at_least_one_condition(self) -> 'DisableTestRule':
        if self.expression is None and self.targets is None and self.configs is None:
            raise ValueError(
                'at least one of the expression, `targets` or `configs` must be provided. '
                'For example: @pytest.mark.disable_test'
                '(\'IDF_TARGET == "esp32"\', reason="IDF-1234, will fix it ASAP")'
            )
        return self

    def matches(self, targets: t.Sequence[str], configs: t.Sequence[str]) -> bool:
        """Check whether this rule disables a test case.

        A multi-DUT test case cannot run partially, so the expression disables the whole
        case as soon as it evaluates to true for one of its DUTs.

        :param targets: Per-DUT targets of the test case
        :param configs: Per-DUT sdkconfig names of the test case

        :returns: True if all the given conditions match

        :raises DisableTestError: If the expression cannot be evaluated, e.g. when it
            uses a SOC header macro and ``IDF_PATH`` is not set
        """
        if not _selectors_match(self.targets, targets):
            return False

        if not _selectors_match(self.configs, configs):
            return False

        if self.expression is not None and not any(
            self._evaluate(target, config) for target, config in zip(targets, configs)
        ):
            return False

        return True

    def _evaluate(self, target: str, config: str) -> t.Any:
        """Evaluate the expression one target-config pair.

        :param target: Target
        :param config: Sdkconfig name

        :returns: Value the expression evaluates to

        :raises DisableTestError: If the expression cannot be parsed or evaluated
        """
        try:
            return parse_bool_expr(self.expression).get_value(target, config)  # type: ignore[arg-type]
        except Exception as e:  # esp-bool-parser raises various types
            raise DisableTestError(
                f'failed to evaluate expression {self.expression!r} for target {target!r}, config {config!r}: {e}'
            ) from e

    @property
    def report_reason(self) -> str:
        """Reason to show in the reports, never empty."""
        return self.reason or 'disabled by the `disable_test` marker'

    def __repr__(self) -> str:
        parts = []
        if self.expression:
            parts.append(repr(self.expression))
        if self.targets is not None:
            parts.append(f'targets={[",".join(s) for s in self.targets]}')
        if self.configs is not None:
            parts.append(f'configs={[",".join(s) for s in self.configs]}')
        if self.reason:
            parts.append(f'reason={self.reason!r}')
        return f'disable_test({", ".join(parts)})'


def parse_disable_test_marker(item: pytest.Item) -> t.Optional[DisableTestRule]:
    """Get and validate the closest ``disable_test`` marker of a test item.

    :param item: The pytest test item

    :returns: The validated rule, or None if the item has no ``disable_test`` marker

    :raises pytest.UsageError: If the marker is invalid
    """
    marker = item.get_closest_marker('disable_test')
    if marker is None:
        return None

    try:
        rule = DisableTestRule.model_validate(marker)
    except ValidationError as e:
        raise pytest.UsageError(f'{item.nodeid}: `disable_test` marker is invalid: {e}') from e

    if not rule.reason:
        logger.warning(
            '%s: `disable_test` marker has no `reason`.',
            item.nodeid,
        )

    return rule
