# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import os

import pytest
from pydantic import ValidationError

from idf_ci.idf_pytest.markers import (
    DisableTestError,
    DisableTestRule,
    parse_disable_test_marker,
)


def make_rule(*args, **kwargs) -> DisableTestRule:
    return DisableTestRule.model_validate(pytest.mark.disable_test(*args, **kwargs).mark)


class TestDisableTestRuleValidation:
    def test_expression_only(self):
        rule = make_rule('IDF_TARGET == "esp32"')
        assert rule.expression == 'IDF_TARGET == "esp32"'
        assert rule.targets is None
        assert rule.configs is None
        assert rule.reason == ''

    def test_targets_and_configs_normalized(self):
        rule = make_rule(targets='esp32', configs=['iram', 'default'], reason=' IDF-1234 ')
        assert rule.targets == (('esp32',),)
        assert rule.configs == (('iram',), ('default',))
        assert rule.reason == 'IDF-1234'

    def test_selectors_are_split_on_commas(self):
        rule = make_rule(targets=['esp32,*', ' esp32c3 , esp32c3 '])
        assert rule.targets == (('esp32', '*'), ('esp32c3', 'esp32c3'))

    def test_empty_selector_value(self):
        with pytest.raises(ValidationError, match='contains an empty value'):
            make_rule(targets=['esp32,'])

    def test_nothing_specified(self):
        with pytest.raises(ValidationError, match='at least one of'):
            make_rule(reason='why not')

    def test_too_many_positional_args(self):
        with pytest.raises(ValidationError, match='at most one positional argument'):
            make_rule('IDF_TARGET == "esp32"', 'IDF_TARGET == "esp32c3"')

    def test_unknown_kwarg(self):
        with pytest.raises(ValidationError, match='unknown keyword argument'):
            make_rule(targets=['esp32'], target='esp32')

    @pytest.mark.parametrize('expression', ['', '   ', 1, None])
    def test_invalid_expression_type(self, expression):
        with pytest.raises(ValidationError, match='expression must be a non-empty string'):
            make_rule(expression)

    @pytest.mark.parametrize('value', [[], '', ['esp32', ''], ['esp32', 1], 42])
    def test_invalid_targets(self, value):
        with pytest.raises(ValidationError, match='`targets` must be'):
            make_rule(targets=value)

    @pytest.mark.parametrize('value', [[], ['default', None], 42])
    def test_invalid_configs(self, value):
        with pytest.raises(ValidationError, match='`configs` must be'):
            make_rule(configs=value)

    def test_invalid_reason_type(self):
        with pytest.raises(ValidationError, match='`reason` must be a string'):
            make_rule(targets=['esp32'], reason=1234)

    def test_unparsable_expression(self):
        # the expression is parsed while it is evaluated, not while the marker is parsed
        rule = make_rule('IDF_TARGET ==')
        with pytest.raises(DisableTestError, match='failed to evaluate expression'):
            rule.matches(['esp32'], ['default'])

    def test_report_reason_fallback(self):
        assert make_rule(targets=['esp32']).report_reason == 'disabled by the `disable_test` marker'
        assert make_rule(targets=['esp32'], reason='IDF-1234').report_reason == 'IDF-1234'


class TestDisableTestRuleMatches:
    @pytest.mark.parametrize(
        ('args', 'kwargs', 'targets', 'configs', 'expected'),
        [
            # targets only, single DUT
            ((), {'targets': ['esp32']}, ['esp32'], ['default'], True),
            ((), {'targets': ['esp32']}, ['esp32c3'], ['default'], False),
            ((), {'targets': ['esp32', 'esp32c3']}, ['esp32c3'], ['default'], True),
            # configs only
            ((), {'configs': ['iram']}, ['esp32'], ['iram'], True),
            ((), {'configs': ['iram']}, ['esp32'], ['default'], False),
            # expression only
            (('IDF_TARGET == "esp32"',), {}, ['esp32'], ['default'], True),
            (('IDF_TARGET == "esp32"',), {}, ['esp32c3'], ['default'], False),
            (('CONFIG_NAME == "iram"',), {}, ['esp32'], ['iram'], True),
            # all conditions are ANDed
            (('CONFIG_NAME == "iram"',), {'targets': ['esp32']}, ['esp32'], ['iram'], True),
            (('CONFIG_NAME == "iram"',), {'targets': ['esp32']}, ['esp32'], ['default'], False),
            ((), {'targets': ['esp32'], 'configs': ['iram']}, ['esp32'], ['iram'], True),
            ((), {'targets': ['esp32'], 'configs': ['iram']}, ['esp32c3'], ['iram'], False),
            # plain target matches any DUT of a multi-DUT case
            ((), {'targets': ['esp32c3']}, ['esp32', 'esp32c3'], ['default', 'default'], True),
            ((), {'targets': ['esp32s2']}, ['esp32', 'esp32c3'], ['default', 'default'], False),
            # expression matches when any DUT satisfies it
            (('IDF_TARGET == "esp32c3"',), {}, ['esp32', 'esp32c3'], ['default', 'default'], True),
            (('IDF_TARGET == "esp32s2"',), {}, ['esp32', 'esp32c3'], ['default', 'default'], False),
            # multi-DUT selectors
            ((), {'targets': ['esp32,esp32c3']}, ['esp32', 'esp32c3'], ['default', 'default'], True),
            ((), {'targets': ['esp32c3,esp32']}, ['esp32', 'esp32c3'], ['default', 'default'], False),
            ((), {'targets': ['esp32,*']}, ['esp32', 'esp32c3'], ['default', 'default'], True),
            ((), {'targets': ['*,esp32c3']}, ['esp32', 'esp32c3'], ['default', 'default'], True),
            ((), {'targets': ['*,esp32']}, ['esp32', 'esp32c3'], ['default', 'default'], False),
            # a selector only matches a case with the same number of DUTs
            ((), {'targets': ['esp32,*']}, ['esp32'], ['default'], False),
            ((), {'targets': ['esp32,*']}, ['esp32', 'esp32', 'esp32'], ['default'] * 3, False),
            # a bare wildcard matches any case
            ((), {'targets': ['*']}, ['esp32'], ['default'], True),
            ((), {'targets': ['*']}, ['esp32', 'esp32c3'], ['default', 'default'], True),
            # config selectors work the same way
            ((), {'configs': ['default,iram']}, ['esp32', 'esp32'], ['default', 'iram'], True),
            ((), {'configs': ['*,iram']}, ['esp32', 'esp32'], ['default', 'iram'], True),
            ((), {'configs': ['*,iram']}, ['esp32', 'esp32'], ['default', 'default'], False),
            # any of the given selectors may match
            ((), {'targets': ['esp32s2,*', '*,esp32c3']}, ['esp32', 'esp32c3'], ['default', 'default'], True),
        ],
    )
    def test_matches(self, args, kwargs, targets, configs, expected):
        assert make_rule(*args, **kwargs).matches(targets, configs) is expected

    @pytest.mark.skipif(not os.getenv('IDF_PATH'), reason='IDF_PATH is not set')
    def test_env_var_in_expression(self, monkeypatch):
        # esp-bool-parser resolves unknown CAPS attributes from the environment,
        # which is how a "CI only" disable is expressed. An unset variable evaluates
        # to the integer 0, so always compare against the expected value.
        monkeypatch.setenv('IDF_CI_FAKE_JOB', '1')
        assert make_rule('IDF_CI_FAKE_JOB == "1"', reason='CI only').matches(['esp32'], ['default']) is True
        assert make_rule('IDF_CI_FAKE_UNSET_JOB == "1"', reason='CI only').matches(['esp32'], ['default']) is False

    def test_unevaluatable_expression(self, monkeypatch):
        # resolving an unknown attribute needs the SOC headers, which need IDF_PATH
        monkeypatch.delenv('IDF_PATH', raising=False)
        rule = make_rule('IDF_CI_FAKE_UNKNOWN_ATTR == "1"', reason='needs IDF_PATH')
        with pytest.raises(DisableTestError, match='failed to evaluate expression'):
            rule.matches(['esp32xx-not-a-target'], ['default'])


class TestParseDisableTestMarker:
    class FakeItem:
        nodeid = 'test_foo.py::test_foo'

        def __init__(self, *marks):
            self._marks = marks

        def get_closest_marker(self, name):
            # the closest marker is the first one of pytest's bottom-up order
            for m in self._marks:
                if m.mark.name == name:
                    return m.mark
            return None

    def test_closest_marker_wins(self):
        item = self.FakeItem(
            pytest.mark.disable_test(targets=['esp32'], reason='closest'),
            pytest.mark.disable_test(targets=['esp32c3'], reason='outer'),
            pytest.mark.nightly_run,
        )
        rule = parse_disable_test_marker(item)
        assert rule.reason == 'closest'

    def test_no_marker(self):
        assert parse_disable_test_marker(self.FakeItem()) is None

    def test_invalid_marker_raises_usage_error(self):
        item = self.FakeItem(pytest.mark.disable_test(reason='no condition'))
        with pytest.raises(pytest.UsageError, match=r'test_foo.py::test_foo: `disable_test` marker is invalid'):
            parse_disable_test_marker(item)

    def test_missing_reason_warns(self, caplog):
        # other tests call setup_logging(), which turns off propagation
        logger = logging.getLogger('idf_ci.idf_pytest.markers')
        with caplog.at_level(logging.WARNING, logger=logger.name):
            logger.addHandler(caplog.handler)
            try:
                rule = parse_disable_test_marker(self.FakeItem(pytest.mark.disable_test(targets=['esp32'])))
            finally:
                logger.removeHandler(caplog.handler)

        assert rule is not None
        assert 'has no `reason`' in caplog.text
