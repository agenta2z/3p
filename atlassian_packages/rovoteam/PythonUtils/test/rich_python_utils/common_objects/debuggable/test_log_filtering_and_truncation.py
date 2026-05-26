"""
Tests for Debuggable log type filtering, message length control,
named loggers, and overflow strategies.
"""

import logging
import re

import pytest


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from a string."""
    return re.sub(r'\x1b\[[0-9;]*m', '', text)

from python_utils.common_objects.debuggable import (
    Debuggable, Debugger, LoggerConfig,
    DEFAULT_LOG_TYPE, LOG_TYPE_PARENT_CHILD_DEBUGGABLE_LINK,
)


# Helper: capture callable that records all log calls
def make_capture():
    messages = []

    def capture(msg):
        messages.append(msg)

    capture.messages = messages
    return capture


def make_dict_capture():
    items = []

    def capture(log_data):
        items.append(log_data)

    capture.items = items
    return capture


class ConcreteDebuggable(Debuggable):
    """Concrete subclass for testing."""
    pass


# =============================================================================
# Class 1: TestNamedLoggers
# =============================================================================
class TestNamedLoggers:
    """Dict-based logger naming and inline config."""

    def test_dict_logger_basic(self):
        cap = make_capture()
        d = ConcreteDebuggable(
            logger={'console': cap},
            always_add_logging_based_logger=False,
            log_time=False,
            console_loggers_or_logger_types=(cap,),
        )
        d.log_info("hello")
        assert len(cap.messages) == 1

    def test_dict_logger_multiple(self):
        cap1 = make_dict_capture()
        cap2 = make_dict_capture()
        d = ConcreteDebuggable(
            logger={'a': cap1, 'b': cap2},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("hello")
        assert len(cap1.items) == 1
        assert len(cap2.items) == 1

    def test_auto_naming_single_print(self):
        d = ConcreteDebuggable(
            logger=print,
            always_add_logging_based_logger=False,
            log_time=False,
        )
        assert isinstance(d.logger, dict)
        assert 'print' in d.logger
        assert d.logger['print'] is print

    def test_auto_naming_logging_logger(self):
        lg = logging.getLogger('test_auto_naming_lg')
        d = ConcreteDebuggable(
            logger=lg,
            always_add_logging_based_logger=False,
            log_time=False,
        )
        assert isinstance(d.logger, dict)
        assert 'test_auto_naming_lg' in d.logger

    def test_auto_naming_callable(self):
        def my_custom_logger(data):
            pass

        d = ConcreteDebuggable(
            logger=my_custom_logger,
            always_add_logging_based_logger=False,
            log_time=False,
        )
        assert isinstance(d.logger, dict)
        assert 'my_custom_logger' in d.logger

    def test_auto_naming_tuple(self):
        cap1 = make_dict_capture()
        cap2 = make_dict_capture()
        d = ConcreteDebuggable(
            logger=(cap1, cap2),
            always_add_logging_based_logger=False,
            log_time=False,
        )
        assert isinstance(d.logger, dict)
        assert len(d.logger) == 2

    def test_default_logger_name_for_auto_added(self):
        d = ConcreteDebuggable(
            always_add_logging_based_logger=True,
            log_time=False,
        )
        assert isinstance(d.logger, dict)
        assert '_default' in d.logger
        assert isinstance(d.logger['_default'], logging.Logger)

    def test_inline_config_tuple_in_tuple(self):
        cap = make_dict_capture()
        cfg = LoggerConfig(show_logger_name=True)
        d = ConcreteDebuggable(
            logger=(print, (cap, cfg)),
            always_add_logging_based_logger=False,
            log_time=False,
        )
        assert isinstance(d.logger, dict)
        assert len(d.logger) == 2
        # Config should be resolved for the capture logger
        cap_name = [n for n, l in d.logger.items() if l is cap][0]
        assert d._resolved_logger_configs.get(cap_name) is cfg

    def test_inline_config_tuple_in_dict(self):
        cap = make_dict_capture()
        cfg = LoggerConfig(show_logger_name=True)
        d = ConcreteDebuggable(
            logger={'my_logger': (cap, cfg)},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        assert d.logger['my_logger'] is cap
        assert d._resolved_logger_configs['my_logger'] is cfg

    def test_inline_config_auto_generates_name(self):
        cap = make_dict_capture()
        cfg = LoggerConfig(show_logger_name=True)
        d = ConcreteDebuggable(
            logger=(cap, cfg),
            always_add_logging_based_logger=False,
            log_time=False,
        )
        assert isinstance(d.logger, dict)
        assert len(d.logger) == 1
        name = list(d.logger.keys())[0]
        assert d.logger[name] is cap
        assert d._resolved_logger_configs[name] is cfg

    def test_inline_config_priority_over_logger_configs(self):
        cap = make_dict_capture()
        inline_cfg = LoggerConfig(enabled_log_types={'Error'})
        dict_cfg = LoggerConfig(enabled_log_types={'Error', 'Data'})
        d = ConcreteDebuggable(
            logger={'a': (cap, inline_cfg)},
            logger_configs={'a': dict_cfg},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        # Inline should win
        assert d._resolved_logger_configs['a'] is inline_cfg

    def test_resolved_logger_configs_merges_both_sources(self):
        cap1 = make_dict_capture()
        cap2 = make_dict_capture()
        inline_cfg = LoggerConfig(enabled_log_types={'Error'})
        dict_cfg = LoggerConfig(enabled_log_types={'Error', 'Data'})
        d = ConcreteDebuggable(
            logger={'a': (cap1, inline_cfg), 'b': cap2},
            logger_configs={'b': dict_cfg},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        assert d._resolved_logger_configs['a'] is inline_cfg
        assert d._resolved_logger_configs['b'] is dict_cfg


# =============================================================================
# Class 2: TestLogTypeFiltering
# =============================================================================
class TestLogTypeFiltering:
    """Instance-level log type filtering."""

    def test_no_filtering_by_default(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger=cap,
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("msg1", "TypeA")
        d.log_info("msg2", "TypeB")
        assert len(cap.items) == 2

    def test_enabled_log_types_whitelist(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger=cap,
            always_add_logging_based_logger=False,
            log_time=False,
            enabled_log_types={'Error', 'Data'},
        )
        d.log_info("msg1", "Error")
        d.log_info("msg2", "Data")
        d.log_info("msg3", "Other")
        assert len(cap.items) == 2
        assert all(item['type'] in ('Error', 'Data') for item in cap.items)

    def test_disabled_log_types_blacklist(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger=cap,
            always_add_logging_based_logger=False,
            log_time=False,
            disabled_log_types={'Debug'},
        )
        d.log_info("msg1", "Error")
        d.log_info("msg2", "Debug")
        d.log_info("msg3", "Info")
        assert len(cap.items) == 2
        assert all(item['type'] != 'Debug' for item in cap.items)

    def test_enabled_and_disabled_combined(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger=cap,
            always_add_logging_based_logger=False,
            log_time=False,
            enabled_log_types={'Error', 'Warning', 'Data'},
            disabled_log_types={'Data'},
        )
        d.log_info("msg1", "Error")
        d.log_info("msg2", "Data")
        d.log_info("msg3", "Warning")
        d.log_info("msg4", "Other")
        assert len(cap.items) == 2
        types = {item['type'] for item in cap.items}
        assert types == {'Error', 'Warning'}

    def test_empty_enabled_set_silences_all(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger=cap,
            always_add_logging_based_logger=False,
            log_time=False,
            enabled_log_types=set(),
        )
        d.log_info("msg1", "Error")
        d.log_info("msg2")
        assert len(cap.items) == 0

    def test_default_log_type_subject_to_filtering(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger=cap,
            always_add_logging_based_logger=False,
            log_time=False,
            enabled_log_types={'Error'},
        )
        d.log_info("msg1")  # default type is 'Message'
        assert len(cap.items) == 0

    def test_parent_child_link_type_subject_to_filtering(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger=cap,
            always_add_logging_based_logger=False,
            log_time=False,
            disabled_log_types={LOG_TYPE_PARENT_CHILD_DEBUGGABLE_LINK},
        )
        parent = Debugger(logger=cap, always_add_logging_based_logger=False, log_time=False)
        d.set_parent_debuggable(parent)
        # The link log should have been filtered out
        link_logs = [item for item in cap.items if item.get('type') == LOG_TYPE_PARENT_CHILD_DEBUGGABLE_LINK]
        assert len(link_logs) == 0


# =============================================================================
# Class 3: TestLoggerConfigTypeFiltering
# =============================================================================
class TestLoggerConfigTypeFiltering:
    """Per-logger log type filtering via logger_configs and inline."""

    def test_per_logger_enabled_types_via_logger_configs(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger={'a': cap},
            logger_configs={'a': LoggerConfig(enabled_log_types={'Error'})},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("msg1", "Error")
        d.log_info("msg2", "Data")
        assert len(cap.items) == 1
        assert cap.items[0]['type'] == 'Error'

    def test_per_logger_disabled_types_via_logger_configs(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger={'a': cap},
            logger_configs={'a': LoggerConfig(disabled_log_types={'Debug'})},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("msg1", "Error")
        d.log_info("msg2", "Debug")
        d.log_info("msg3", "Info")
        assert len(cap.items) == 2
        assert all(item['type'] != 'Debug' for item in cap.items)

    def test_per_logger_enabled_types_via_inline(self):
        cap = make_dict_capture()
        cfg = LoggerConfig(enabled_log_types={'Error'})
        d = ConcreteDebuggable(
            logger=(cap, cfg),
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("msg1", "Error")
        d.log_info("msg2", "Data")
        assert len(cap.items) == 1
        assert cap.items[0]['type'] == 'Error'

    def test_one_logger_filtered_other_not(self):
        cap1 = make_dict_capture()
        cap2 = make_dict_capture()
        d = ConcreteDebuggable(
            logger={'filtered': cap1, 'unfiltered': cap2},
            logger_configs={'filtered': LoggerConfig(enabled_log_types={'Error'})},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("msg1", "Error")
        d.log_info("msg2", "Data")
        assert len(cap1.items) == 1  # only Error
        assert len(cap2.items) == 2  # both

    def test_instance_and_logger_config_gates_stack(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger={'a': cap},
            logger_configs={'a': LoggerConfig(enabled_log_types={'Error', 'Warning'})},
            disabled_log_types={'Warning'},  # instance-level blocks Warning
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("msg1", "Error")
        d.log_info("msg2", "Warning")
        assert len(cap.items) == 1
        assert cap.items[0]['type'] == 'Error'

    def test_logger_config_key_not_matching_any_logger(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger={'a': cap},
            logger_configs={'nonexistent': LoggerConfig(enabled_log_types={'Error'})},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("msg1", "Data")
        assert len(cap.items) == 1  # no error, config ignored


# =============================================================================
# Class 4: TestShowLoggerName
# =============================================================================
class TestShowLoggerName:
    """Logger name in output."""

    def test_show_logger_name_in_print_output(self, capsys):
        d = ConcreteDebuggable(
            logger={'console': print},
            logger_configs={'console': LoggerConfig(show_logger_name=True)},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("hello", "Test")
        captured = _strip_ansi(capsys.readouterr().out)
        assert '[console]' in captured

    def test_show_logger_name_false_by_default(self, capsys):
        d = ConcreteDebuggable(
            logger={'console': print},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("hello", "Test")
        captured = capsys.readouterr()
        assert '[console]' not in captured.out

    def test_show_logger_name_in_callable_dict(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger={'my_backend': cap},
            logger_configs={'my_backend': LoggerConfig(show_logger_name=True)},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("hello", "Test")
        assert cap.items[0].get('logger_name') == 'my_backend'

    def test_show_logger_name_per_logger(self, capsys):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger={'show': print, 'hide': cap},
            logger_configs={
                'show': LoggerConfig(show_logger_name=True),
                # 'hide' has no config, default show_logger_name=False
            },
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("hello", "Test")
        captured = _strip_ansi(capsys.readouterr().out)
        assert '[show]' in captured
        assert 'logger_name' not in cap.items[0]


# =============================================================================
# Class 5: TestIsLogTypeEnabled
# =============================================================================
class TestIsLogTypeEnabled:
    """Direct testing of _is_log_type_enabled helper."""

    def test_all_none_returns_true(self):
        d = Debugger(logger=print, always_add_logging_based_logger=False, log_time=False)
        assert d._is_log_type_enabled('AnyType') is True

    def test_instance_whitelist_only(self):
        d = Debugger(
            logger=print, always_add_logging_based_logger=False, log_time=False,
            enabled_log_types={'Error', 'Warning'},
        )
        assert d._is_log_type_enabled('Error') is True
        assert d._is_log_type_enabled('Data') is False

    def test_instance_blacklist_only(self):
        d = Debugger(
            logger=print, always_add_logging_based_logger=False, log_time=False,
            disabled_log_types={'Debug'},
        )
        assert d._is_log_type_enabled('Debug') is False
        assert d._is_log_type_enabled('Error') is True

    def test_logger_config_whitelist(self):
        d = Debugger(logger=print, always_add_logging_based_logger=False, log_time=False)
        cfg = LoggerConfig(enabled_log_types={'Error'})
        assert d._is_log_type_enabled('Error', cfg) is True
        assert d._is_log_type_enabled('Data', cfg) is False

    def test_logger_config_blacklist(self):
        d = Debugger(logger=print, always_add_logging_based_logger=False, log_time=False)
        cfg = LoggerConfig(disabled_log_types={'Debug'})
        assert d._is_log_type_enabled('Debug', cfg) is False
        assert d._is_log_type_enabled('Error', cfg) is True

    def test_both_gates_must_pass(self):
        d = Debugger(
            logger=print, always_add_logging_based_logger=False, log_time=False,
            enabled_log_types={'Error', 'Warning'},
        )
        cfg = LoggerConfig(disabled_log_types={'Warning'})
        assert d._is_log_type_enabled('Error', cfg) is True
        assert d._is_log_type_enabled('Warning', cfg) is False  # blocked by per-logger
        assert d._is_log_type_enabled('Data', cfg) is False  # blocked by instance


# =============================================================================
# Class 7: TestBackwardCompatibility
# =============================================================================
class TestBackwardCompatibility:
    """Existing behavior preserved."""

    def test_plain_logger_still_works(self, capsys):
        d = ConcreteDebuggable(
            logger=print,
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("hello world")
        captured = capsys.readouterr()
        assert 'hello world' in captured.out

    def test_tuple_logger_still_works(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger=(print, cap),
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("hello")
        assert len(cap.items) == 1

    def test_callable_logger_receives_same_dict_structure(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger=cap,
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info("hello", "Test")
        data = cap.items[0]
        assert 'level' in data
        assert 'name' in data
        assert 'id' in data
        assert 'type' in data
        assert 'item' in data
        assert data['level'] == logging.INFO
        assert data['type'] == 'Test'

    def test_log_level_filtering_unchanged(self):
        cap = make_dict_capture()
        d = ConcreteDebuggable(
            logger=cap,
            always_add_logging_based_logger=False,
            log_time=False,
            log_level=logging.WARNING,
        )
        d.log_info("should be filtered")
        d.log_warning("should appear")
        assert len(cap.items) == 1
        assert cap.items[0]['level'] == logging.WARNING

    def test_rate_limiting_unchanged(self):
        cap = make_capture()
        d = ConcreteDebuggable(
            logger=cap,
            always_add_logging_based_logger=False,
            log_time=False,
            console_display_rate_limit=0.5,
            console_loggers_or_logger_types=(cap,),
        )
        d.log_info("msg1")
        d.log_info("msg2")
        # Second message should be rate-limited
        assert len(cap.messages) == 1

    def test_console_logger_detection_unchanged(self):
        d = ConcreteDebuggable(logger=print, always_add_logging_based_logger=False, log_time=False)
        assert d._is_console_logger(print) is True

        def my_backend(data):
            pass
        assert d._is_console_logger(my_backend) is False


# =============================================================================
# Class 11: TestConfigCopying
# =============================================================================
class TestConfigCopying:
    """New attributes in config copy operations."""

    def test_copy_logging_config_copies_new_attrs(self):
        source = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            log_time=False,
            enabled_log_types={'Error'},
            disabled_log_types={'Debug'},
            logger_configs={'x': LoggerConfig(show_logger_name=True)},
        )
        target = Debugger(logger=print, always_add_logging_based_logger=False, log_time=False)
        target.copy_logging_config(source)
        assert target.enabled_log_types == {'Error'}
        assert target.disabled_log_types == {'Debug'}

    def test_copy_debuggable_config_from_copies_new_attrs(self):
        source = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            log_time=False,
            enabled_log_types={'Error'},
        )
        target = Debugger(
            logger=print,
            always_add_logging_based_logger=False,
            log_time=False,
            copy_debuggable_config_from=source,
        )
        assert target.enabled_log_types == {'Error'}


# =============================================================================
# Class 12: TestLoggerPipeline
# =============================================================================
class TestLoggerPipeline:
    """Test pass_output and use_processed pipeline flags in LoggerConfig."""

    def test_pass_output_captures_return_value(self):
        """Callable logger with pass_output=True has its return captured."""
        upstream_items = []
        downstream_items = []

        def upstream_logger(log_data, **kwargs):
            upstream_items.append(log_data)
            return {'processed': True, 'original_type': log_data.get('type')}

        def downstream_logger(log_data, **kwargs):
            downstream_items.append(log_data)

        d = ConcreteDebuggable(
            logger={
                'upstream': (upstream_logger, LoggerConfig(pass_output=True)),
                'downstream': (downstream_logger, LoggerConfig(use_processed=True)),
            },
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info({'key': 'value'}, 'TestType')

        assert len(upstream_items) == 1
        assert len(downstream_items) == 1
        # Downstream received the processed dict as 'item'
        assert downstream_items[0]['item'] == {'processed': True, 'original_type': 'TestType'}

    def test_use_processed_without_upstream_uses_original(self):
        """use_processed=True with no upstream pass_output uses original log_item."""
        captured = []

        def logger_fn(log_data, **kwargs):
            captured.append(log_data)

        d = ConcreteDebuggable(
            logger={'only': (logger_fn, LoggerConfig(use_processed=True))},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info({'key': 'value'}, 'TestType')

        assert len(captured) == 1
        assert captured[0]['item']['key'] == 'value'

    def test_default_flags_no_pipeline_effect(self):
        """Default LoggerConfig (pass_output=False, use_processed=False) has no pipeline effect."""
        items_a = []
        items_b = []

        def logger_a(log_data, **kwargs):
            items_a.append(log_data)
            return {'should_be_ignored': True}

        def logger_b(log_data, **kwargs):
            items_b.append(log_data)

        d = ConcreteDebuggable(
            logger={'a': logger_a, 'b': logger_b},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info({'key': 'value'}, 'TestType')

        # Both receive original log_item
        assert items_a[0]['item']['key'] == 'value'
        assert items_b[0]['item']['key'] == 'value'

    def test_pass_output_false_does_not_capture(self):
        """Without pass_output=True, return value is not passed downstream."""
        items_a = []
        items_b = []

        def logger_a(log_data, **kwargs):
            items_a.append(log_data)
            return {'processed': True}

        def logger_b(log_data, **kwargs):
            items_b.append(log_data)

        d = ConcreteDebuggable(
            logger={
                'a': logger_a,  # No LoggerConfig, so pass_output=False by default
                'b': (logger_b, LoggerConfig(use_processed=True)),
            },
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info({'key': 'value'}, 'TestType')

        # b gets original because a didn't have pass_output=True
        assert items_b[0]['item']['key'] == 'value'

    def test_pipeline_with_none_return_preserves_previous_processed(self):
        """If a pass_output logger returns None, processed is not updated."""
        items = []

        def logger_a(log_data, **kwargs):
            return {'from_a': True}

        def logger_b(log_data, **kwargs):
            return None  # Returns None

        def logger_c(log_data, **kwargs):
            items.append(log_data)

        d = ConcreteDebuggable(
            logger={
                'a': (logger_a, LoggerConfig(pass_output=True)),
                'b': (logger_b, LoggerConfig(pass_output=True, use_processed=True)),
                'c': (logger_c, LoggerConfig(use_processed=True)),
            },
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info({'key': 'value'}, 'TestType')

        # c still gets logger_a's output since logger_b returned None
        assert items[0]['item'] == {'from_a': True}

    def test_pipeline_print_logger_receives_processed(self, capsys):
        """Print logger with use_processed=True displays the processed data."""
        def file_logger(log_data, **kwargs):
            return {'compact': 'summary'}

        d = ConcreteDebuggable(
            logger={
                'file': (file_logger, LoggerConfig(pass_output=True)),
                'console': (print, LoggerConfig(use_processed=True)),
            },
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info({'big': 'data'}, 'TestType')

        captured = capsys.readouterr()
        # Print logger should display the processed dict, not the original
        assert 'compact' in captured.out
        assert 'summary' in captured.out


# =============================================================================
# Class 13: TestPassItemKeyAs
# =============================================================================
class TestPassItemKeyAs:
    """Test pass_item_key_as in LoggerConfig."""

    def test_injects_item_key_as_kwarg(self):
        """pass_item_key_as causes Debuggable to inject the item key name as a kwarg."""
        received_kwargs = {}

        def logger_fn(log_data, **kwargs):
            received_kwargs.update(kwargs)

        d = ConcreteDebuggable(
            logger={
                'file': (logger_fn, LoggerConfig(pass_item_key_as='parts_key_path_root')),
            },
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info({'key': 'value'}, 'TestType')

        assert 'parts_key_path_root' in received_kwargs
        assert received_kwargs['parts_key_path_root'] == 'item'

    def test_per_call_override_takes_precedence(self):
        """Explicit per-call kwarg overrides pass_item_key_as injection."""
        received_kwargs = {}

        def logger_fn(log_data, **kwargs):
            received_kwargs.update(kwargs)

        d = ConcreteDebuggable(
            logger={
                'file': (logger_fn, LoggerConfig(pass_item_key_as='parts_key_path_root')),
            },
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info({'key': 'value'}, 'TestType', parts_key_path_root='custom_root')

        assert received_kwargs['parts_key_path_root'] == 'custom_root'

    def test_no_injection_without_config(self):
        """Without pass_item_key_as, no extra kwarg is injected."""
        received_kwargs = {}

        def logger_fn(log_data, **kwargs):
            received_kwargs.update(kwargs)

        d = ConcreteDebuggable(
            logger={'file': logger_fn},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info({'key': 'value'}, 'TestType')

        assert 'parts_key_path_root' not in received_kwargs

    def test_different_kwarg_name(self):
        """pass_item_key_as works with any kwarg name."""
        received_kwargs = {}

        def logger_fn(log_data, **kwargs):
            received_kwargs.update(kwargs)

        d = ConcreteDebuggable(
            logger={
                'file': (logger_fn, LoggerConfig(pass_item_key_as='data_root')),
            },
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info({'key': 'value'}, 'TestType')

        assert received_kwargs['data_root'] == 'item'


# =============================================================================
# Class 14: TestLoggerConfigMaxMessageLength
# =============================================================================
class TestLoggerConfigMaxMessageLength:
    """LoggerConfig.get_max_message_length resolution."""

    def test_no_limits_returns_none(self):
        cfg = LoggerConfig()
        assert cfg.get_max_message_length('Data') is None

    def test_global_max_only(self):
        cfg = LoggerConfig(max_message_length=500)
        assert cfg.get_max_message_length('Data') == 500
        assert cfg.get_max_message_length('Error') == 500

    def test_per_type_max_only(self):
        cfg = LoggerConfig(max_message_length_by_log_type={'Data': 200})
        assert cfg.get_max_message_length('Data') == 200
        assert cfg.get_max_message_length('Error') is None

    def test_strictest_wins(self):
        cfg = LoggerConfig(
            max_message_length=500,
            max_message_length_by_log_type={'Data': 200},
        )
        assert cfg.get_max_message_length('Data') == 200
        assert cfg.get_max_message_length('Error') == 500

    def test_global_stricter_than_per_type(self):
        cfg = LoggerConfig(
            max_message_length=100,
            max_message_length_by_log_type={'Data': 500},
        )
        assert cfg.get_max_message_length('Data') == 100

    def test_zero_treated_as_no_limit(self):
        cfg = LoggerConfig(max_message_length=0)
        assert cfg.get_max_message_length('Data') is None

    def test_negative_treated_as_no_limit(self):
        cfg = LoggerConfig(max_message_length=-1)
        assert cfg.get_max_message_length('Data') is None


# =============================================================================
# Class 15: TestMaxMessageLengthPassthrough
# =============================================================================
class TestMaxMessageLengthPassthrough:
    """Debuggable passes resolved max_message_length to callable loggers."""

    def test_passed_as_kwarg(self):
        received_kwargs = {}

        def logger_fn(log_data, **kwargs):
            received_kwargs.update(kwargs)

        d = ConcreteDebuggable(
            logger={
                'file': (logger_fn, LoggerConfig(max_message_length=5000)),
            },
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info('hello', 'Data')

        assert received_kwargs.get('max_message_length') == 5000

    def test_per_type_resolves_correctly(self):
        received_kwargs = []

        def logger_fn(log_data, **kwargs):
            received_kwargs.append(dict(kwargs))

        cfg = LoggerConfig(
            max_message_length=1000,
            max_message_length_by_log_type={'Data': 200},
        )
        d = ConcreteDebuggable(
            logger={'file': (logger_fn, cfg)},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info('hello', 'Data')
        d.log_info('hello', 'Error')

        assert received_kwargs[0].get('max_message_length') == 200
        assert received_kwargs[1].get('max_message_length') == 1000

    def test_not_passed_when_no_limit(self):
        received_kwargs = {}

        def logger_fn(log_data, **kwargs):
            received_kwargs.update(kwargs)

        d = ConcreteDebuggable(
            logger={'file': (logger_fn, LoggerConfig())},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info('hello', 'Data')

        assert 'max_message_length' not in received_kwargs


class TestConsoleMaxMessageLength:
    """Console loggers truncate via LoggerConfig.max_message_length."""

    def test_truncated_when_over_limit(self, capsys):
        """Print output is truncated with '... [N chars]' suffix."""
        long_msg = 'x' * 500
        d = ConcreteDebuggable(
            logger={
                'console': (print, LoggerConfig(max_message_length=100)),
            },
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info(long_msg, 'Data')
        out = _strip_ansi(capsys.readouterr().out)
        assert '... [500 chars]' in out
        # The full 500-char message should NOT appear
        assert long_msg not in out

    def test_not_truncated_when_under_limit(self, capsys):
        """Short messages pass through unchanged."""
        short_msg = 'hello'
        d = ConcreteDebuggable(
            logger={
                'console': (print, LoggerConfig(max_message_length=100)),
            },
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info(short_msg, 'Data')
        out = _strip_ansi(capsys.readouterr().out)
        assert 'hello' in out
        assert 'chars]' not in out

    def test_no_truncation_without_config(self, capsys):
        """No LoggerConfig on console → no truncation."""
        long_msg = 'y' * 500
        d = ConcreteDebuggable(
            logger=print,
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info(long_msg, 'Data')
        out = _strip_ansi(capsys.readouterr().out)
        # No truncation indicator
        assert 'chars]' not in out
        # Full content present (may be line-wrapped, so check joined)
        assert long_msg in out.replace('\n', '')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
