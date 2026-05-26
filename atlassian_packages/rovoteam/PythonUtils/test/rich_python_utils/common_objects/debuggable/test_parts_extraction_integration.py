"""
Test the Debuggable → write_json integration for parts extraction.

Verifies kwargs forwarding, space handling, and log_data wrapping:
  - Debuggable wraps the original dict under an 'item' key in log_data,
    so parts_key_paths must use 'item.field_name' dotted paths.
  - Debuggable passes space=self.id, which makes the space handler turn
    file_path into a directory and use self.id as the filename inside it.
    E.g. file_path='log.jsonl' → actual file is 'log.jsonl/{d.id}'.
  - Parts dir is co-located: 'log.jsonl/{d.id}.parts/'.
"""

import glob as _glob
import json
import os
from functools import partial

import pytest

from attr import attrs, attrib

from python_utils.common_objects.debuggable import Debuggable, LoggerConfig
from python_utils.io_utils.json_io import write_json, PartsKeyPath, JsonLogger, artifact_field


def _find_parts_file(base_dir, *subdirs, stem, ext):
    """Find a uniquely-named parts file matching the stem and extension."""
    search_dir = os.path.join(base_dir, *subdirs) if subdirs else base_dir
    pattern = os.path.join(search_dir, f'*{stem}*{ext}')
    matches = _glob.glob(pattern)
    assert len(matches) == 1, (
        f"Expected exactly 1 file matching {pattern}, got {len(matches)}: {matches}"
    )
    return matches[0]


class ConcreteDebuggable(Debuggable):
    """Minimal concrete subclass for testing."""
    pass


def _make_mock_action_result():
    """Build a dict mimicking a WebDriverActionResult (attrs class with HTML fields)."""
    return {
        'body_html_before_last_action': '<html><body><h1>Before</h1><p>Old content</p></body></html>',
        'body_html_after_last_action': '<html><body><h1>After</h1><p>New content</p></body></html>',
        'cleaned_body_html_after_last_action': '<div><h1>After</h1><p>New content</p></div>',
        'is_cleaned_body_html_only_incremental_change': False,
        'source': 'test',
        'action_memory': None,
        'is_follow_up': False,
        'action_skipped': False,
        'skip_reason': None,
    }


# Paths within log_data (Debuggable wraps item under 'item' key)
BEFORE_HTML = 'item.body_html_before_last_action'
AFTER_HTML = 'item.body_html_after_last_action'
CLEANED_HTML = 'item.cleaned_body_html_after_last_action'


class TestPartsExtractionIntegration:
    """Verify that log_info forwards PartsKeyPath kwargs through to write_json."""

    def _create_debuggable(self, log_file_path):
        """Create a Debuggable whose sole logger is a write_json partial."""
        return ConcreteDebuggable(
            debug_mode=True,
            logger=partial(write_json, file_path=log_file_path),
            always_add_logging_based_logger=False,
            log_time=False,
        )

    def _get_actual_paths(self, d, log_file):
        """Derive the actual file and parts dir from the debuggable's space ID.

        Debuggable passes space=self.id to write_json, which turns
        file_path into a directory and uses the id as the filename inside it.
        Parts dir is co-located as {actual_file}.parts/.
        """
        actual_file = os.path.join(log_file, d.id)
        parts_dir = actual_file + '.parts'
        return actual_file, parts_dir

    def test_parts_files_created_through_log_info(self, tmp_path):
        """PartsKeyPath entries passed to log_info produce parts files via write_json."""
        log_file = str(tmp_path / 'actions.jsonl')
        d = self._create_debuggable(log_file)

        d.log_info(
            _make_mock_action_result(),
            'AgentActionResults',
            parts_key_paths=[
                PartsKeyPath(BEFORE_HTML, ext='.html', alias='BeforeHtml', subfolder='ui_source'),
                PartsKeyPath(AFTER_HTML, ext='.html', alias='AfterHtml', subfolder='ui_source'),
                PartsKeyPath(CLEANED_HTML, ext='.html', alias='CleanedHtml', subfolder='ui_source'),
            ],
            parts_min_size=0,
        )

        _, parts_dir = self._get_actual_paths(d, log_file)
        assert os.path.isdir(parts_dir), f'Parts dir not created: {parts_dir}'

        for stem in ('BeforeHtml', 'AfterHtml', 'CleanedHtml'):
            _find_parts_file(parts_dir, 'ui_source', stem=stem, ext='.html')

    def test_parts_file_content_matches_original(self, tmp_path):
        """Extracted parts file content equals the original value from log_item."""
        log_file = str(tmp_path / 'actions.jsonl')
        d = self._create_debuggable(log_file)
        result = _make_mock_action_result()

        d.log_info(
            result,
            'AgentActionResults',
            parts_key_paths=[
                PartsKeyPath(AFTER_HTML, ext='.html', alias='AfterHtml', subfolder='ui_source'),
            ],
            parts_min_size=0,
        )

        _, parts_dir = self._get_actual_paths(d, log_file)
        parts_file = _find_parts_file(parts_dir, 'ui_source', stem='AfterHtml', ext='.html')
        with open(parts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        assert content == result['body_html_after_last_action']

    def test_main_json_has_reference(self, tmp_path):
        """The main JSON replaces extracted values with __parts_file__ references."""
        log_file = str(tmp_path / 'actions.jsonl')
        d = self._create_debuggable(log_file)

        d.log_info(
            _make_mock_action_result(),
            'AgentActionResults',
            parts_key_paths=[
                PartsKeyPath(AFTER_HTML, ext='.html', alias='AfterHtml', subfolder='ui_source'),
            ],
            parts_min_size=0,
        )

        actual_file, _ = self._get_actual_paths(d, log_file)
        with open(actual_file, 'r', encoding='utf-8') as f:
            entry = json.loads(f.readline())

        ref = entry['item']['body_html_after_last_action']
        assert isinstance(ref, dict), f'Expected a reference dict, got {type(ref)}'
        assert '__parts_file__' in ref
        assert 'AfterHtml' in ref['__parts_file__'] and ref['__parts_file__'].endswith('.html')
        assert 'ui_source' in ref['__parts_file__']
        assert ref['__value_type__'] == 'str'

    def test_non_extracted_fields_remain_inline(self, tmp_path):
        """Fields not in parts_key_paths stay as plain values in log_data."""
        log_file = str(tmp_path / 'actions.jsonl')
        d = self._create_debuggable(log_file)

        d.log_info(
            _make_mock_action_result(),
            'AgentActionResults',
            parts_key_paths=[
                PartsKeyPath(AFTER_HTML, ext='.html', subfolder='ui_source'),
            ],
            parts_min_size=0,
        )

        actual_file, _ = self._get_actual_paths(d, log_file)
        with open(actual_file, 'r', encoding='utf-8') as f:
            entry = json.loads(f.readline())

        item = entry['item']
        assert item['source'] == 'test'
        assert item['is_follow_up'] is False


class TestJsonLoggerWithDebuggable:
    """Test JsonLogger as a Debuggable logger with group → subfolder mapping."""

    def _create_debuggable(self, log_file_path):
        return ConcreteDebuggable(
            debug_mode=True,
            logger=JsonLogger(file_path=log_file_path),
            always_add_logging_based_logger=False,
            log_time=False,
        )

    def _get_actual_paths(self, d, log_file):
        actual_file = os.path.join(log_file, d.id)
        parts_dir = actual_file + '.parts'
        return actual_file, parts_dir

    def test_group_creates_subfolder(self, tmp_path):
        """group kwarg passed to log_info becomes subfolder in write_json."""
        log_file = str(tmp_path / 'session.jsonl')
        d = self._create_debuggable(log_file)

        d.log_info({'step': 1}, 'Step', group='iter_0001')

        # subfolder inserts between parent and filename, then space makes it a dir:
        # tmp/session.jsonl → tmp/iter_0001/session.jsonl → tmp/iter_0001/session.jsonl/{d.id}
        actual_file = os.path.join(str(tmp_path), 'iter_0001', 'session.jsonl', d.id)
        assert os.path.isfile(actual_file), f'Expected file at {actual_file}'

    def test_group_with_parts_extraction(self, tmp_path):
        """group + parts_key_paths both work through JsonLogger."""
        log_file = str(tmp_path / 'session.jsonl')
        d = self._create_debuggable(log_file)

        d.log_info(
            _make_mock_action_result(),
            'AgentActionResults',
            group='iter_0001',
            parts_key_paths=[
                PartsKeyPath(AFTER_HTML, ext='.html', alias='AfterHtml', subfolder='ui_source'),
            ],
            parts_min_size=0,
        )

        # subfolder → iter_0001, then space → d.id
        actual_file = os.path.join(str(tmp_path), 'iter_0001', 'session.jsonl', d.id)
        assert os.path.isfile(actual_file)
        _find_parts_file(actual_file + '.parts', 'ui_source', stem='AfterHtml', ext='.html')

    def test_file_path_discoverable(self, tmp_path):
        """JsonLogger.file_path is accessible on the logger instance."""
        log_file = str(tmp_path / 'session.jsonl')
        d = self._create_debuggable(log_file)
        # Find the JsonLogger among resolved loggers
        json_loggers = [
            lgr for lgr in d.logger.values()
            if hasattr(lgr, 'file_path')
        ]
        assert any(lgr.file_path == log_file for lgr in json_loggers)


# Simplified paths (without 'item.' prefix) using parts_key_path_root
BEFORE_HTML_SIMPLE = 'body_html_before_last_action'
AFTER_HTML_SIMPLE = 'body_html_after_last_action'
CLEANED_HTML_SIMPLE = 'cleaned_body_html_after_last_action'


class TestPassItemKeyAsIntegration:
    """Test pass_item_key_as with JsonLogger — simplified paths via parts_key_path_root."""

    def _create_debuggable(self, log_file_path):
        return ConcreteDebuggable(
            debug_mode=True,
            logger={
                'file': (
                    JsonLogger(file_path=log_file_path),
                    LoggerConfig(pass_item_key_as='parts_key_path_root'),
                ),
            },
            always_add_logging_based_logger=False,
            log_time=False,
        )

    def _get_actual_paths(self, d, log_file):
        actual_file = os.path.join(log_file, d.id)
        parts_dir = actual_file + '.parts'
        return actual_file, parts_dir

    def test_simplified_paths_create_parts_files(self, tmp_path):
        """PartsKeyPath with simple field names (no 'item.' prefix) works via pass_item_key_as."""
        log_file = str(tmp_path / 'actions.jsonl')
        d = self._create_debuggable(log_file)

        d.log_info(
            _make_mock_action_result(),
            'AgentActionResults',
            parts_key_paths=[
                PartsKeyPath(BEFORE_HTML_SIMPLE, ext='.html', alias='BeforeHtml', subfolder='ui_source'),
                PartsKeyPath(AFTER_HTML_SIMPLE, ext='.html', alias='AfterHtml', subfolder='ui_source'),
                PartsKeyPath(CLEANED_HTML_SIMPLE, ext='.html', alias='CleanedHtml', subfolder='ui_source'),
            ],
            parts_min_size=0,
        )

        _, parts_dir = self._get_actual_paths(d, log_file)
        assert os.path.isdir(parts_dir)

        for stem in ('BeforeHtml', 'AfterHtml', 'CleanedHtml'):
            _find_parts_file(parts_dir, 'ui_source', stem=stem, ext='.html')

    def test_simplified_paths_content_matches(self, tmp_path):
        """Extracted content from simplified paths matches the original nested value."""
        log_file = str(tmp_path / 'actions.jsonl')
        d = self._create_debuggable(log_file)
        result = _make_mock_action_result()

        d.log_info(
            result,
            'AgentActionResults',
            parts_key_paths=[
                PartsKeyPath(AFTER_HTML_SIMPLE, ext='.html', alias='AfterHtml', subfolder='ui_source'),
            ],
            parts_min_size=0,
        )

        _, parts_dir = self._get_actual_paths(d, log_file)
        parts_file = _find_parts_file(parts_dir, 'ui_source', stem='AfterHtml', ext='.html')
        with open(parts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        assert content == result['body_html_after_last_action']

    def test_simplified_paths_reference_in_json(self, tmp_path):
        """Main JSON has __parts_file__ reference at the correct nested path."""
        log_file = str(tmp_path / 'actions.jsonl')
        d = self._create_debuggable(log_file)

        d.log_info(
            _make_mock_action_result(),
            'AgentActionResults',
            parts_key_paths=[
                PartsKeyPath(AFTER_HTML_SIMPLE, ext='.html', alias='AfterHtml', subfolder='ui_source'),
            ],
            parts_min_size=0,
        )

        actual_file, _ = self._get_actual_paths(d, log_file)
        with open(actual_file, 'r', encoding='utf-8') as f:
            entry = json.loads(f.readline())

        ref = entry['item']['body_html_after_last_action']
        assert isinstance(ref, dict)
        assert '__parts_file__' in ref
        assert 'AfterHtml' in ref['__parts_file__'] and ref['__parts_file__'].endswith('.html')


# ---------------------------------------------------------------------------
# artifacts_as_parts through Debuggable (simulating agent.log_info flow)
# ---------------------------------------------------------------------------

@artifact_field('body_html_before', type='html', group='ui_source')
@artifact_field('body_html_after', type='html', group='ui_source')
@artifact_field('cleaned_html', type='html', group='ui_source')
@attrs(slots=True)
class MockActionResult:
    """Mimics WebDriverActionResult with @artifact_field decorators."""
    body_html_before: str = attrib(default='')
    body_html_after: str = attrib(default='')
    cleaned_html: str = attrib(default='')
    source: str = attrib(default='')
    is_follow_up: bool = attrib(default=False)


def _make_mock_attrs_result():
    return MockActionResult(
        body_html_before='<html><body><h1>Before</h1><p>Old content</p></body></html>',
        body_html_after='<html><body><h1>After</h1><p>New content</p></body></html>',
        cleaned_html='<div><h1>After</h1><p>New content</p></div>',
        source='test',
    )


class TestArtifactsAsPartsThroughDebuggable:
    """Verify artifacts_as_parts kwarg flows from log_info → write_json correctly.

    This simulates the real agent flow:
        self.log_info(action_result, 'AgentActionResults',
                      artifacts_as_parts=True, parts_min_size=0)
    where the action_result class has @artifact_field decorators.
    """

    def _create_debuggable(self, log_file_path):
        return ConcreteDebuggable(
            debug_mode=True,
            logger={
                'file': (
                    JsonLogger(file_path=log_file_path),
                    LoggerConfig(pass_item_key_as='parts_key_path_root'),
                ),
            },
            always_add_logging_based_logger=False,
            log_time=False,
        )

    def _get_actual_paths(self, d, log_file):
        actual_file = os.path.join(log_file, d.id)
        parts_dir = actual_file + '.parts'
        return actual_file, parts_dir

    def test_artifacts_as_parts_creates_files(self, tmp_path):
        """artifacts_as_parts=True on log_info produces parts files for all artifact fields."""
        log_file = str(tmp_path / 'actions.jsonl')
        d = self._create_debuggable(log_file)

        d.log_info(
            _make_mock_attrs_result(),
            'AgentActionResults',
            artifacts_as_parts=True,
            parts_min_size=0,
        )

        _, parts_dir = self._get_actual_paths(d, log_file)
        assert os.path.isdir(parts_dir)

        for stem in ('body_html_before', 'body_html_after', 'cleaned_html'):
            _find_parts_file(parts_dir, 'ui_source', stem=stem, ext='.html')

    def test_artifacts_as_parts_content_matches(self, tmp_path):
        """Extracted artifact file content equals the original field value."""
        log_file = str(tmp_path / 'actions.jsonl')
        d = self._create_debuggable(log_file)
        result = _make_mock_attrs_result()

        d.log_info(
            result,
            'AgentActionResults',
            artifacts_as_parts=True,
            parts_min_size=0,
        )

        _, parts_dir = self._get_actual_paths(d, log_file)
        parts_file = _find_parts_file(parts_dir, 'ui_source', stem='body_html_after', ext='.html')
        with open(parts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        assert content == result.body_html_after

    def test_artifacts_as_parts_reference_in_json(self, tmp_path):
        """Main JSON has __parts_file__ references for extracted artifact fields."""
        log_file = str(tmp_path / 'actions.jsonl')
        d = self._create_debuggable(log_file)

        d.log_info(
            _make_mock_attrs_result(),
            'AgentActionResults',
            artifacts_as_parts=True,
            parts_min_size=0,
        )

        actual_file, _ = self._get_actual_paths(d, log_file)
        with open(actual_file, 'r', encoding='utf-8') as f:
            entry = json.loads(f.readline())

        ref = entry['item']['body_html_after']
        assert isinstance(ref, dict)
        assert '__parts_file__' in ref
        assert 'body_html_after' in ref['__parts_file__'] and ref['__parts_file__'].endswith('.html')
        assert 'ui_source' in ref['__parts_file__']

    def test_non_artifact_fields_remain_inline(self, tmp_path):
        """Fields not decorated with @artifact_field stay as plain values."""
        log_file = str(tmp_path / 'actions.jsonl')
        d = self._create_debuggable(log_file)

        d.log_info(
            _make_mock_attrs_result(),
            'AgentActionResults',
            artifacts_as_parts=True,
            parts_min_size=0,
        )

        actual_file, _ = self._get_actual_paths(d, log_file)
        with open(actual_file, 'r', encoding='utf-8') as f:
            entry = json.loads(f.readline())

        item = entry['item']
        assert item['source'] == 'test'
        assert item['is_follow_up'] is False

    def test_artifacts_as_parts_group_filter(self, tmp_path):
        """artifacts_as_parts=['ui_source'] only extracts that group's artifacts."""
        log_file = str(tmp_path / 'actions.jsonl')
        d = self._create_debuggable(log_file)

        @artifact_field('html', type='html', group='ui')
        @artifact_field('debug_data', type='json', group='debug')
        @attrs(slots=True)
        class MixedResult:
            html: str = attrib(default='')
            debug_data: str = attrib(default='')

        d.log_info(
            MixedResult(html='<h1>Big HTML</h1>', debug_data='{"key": "val"}'),
            'TestResult',
            artifacts_as_parts=['ui'],
            parts_min_size=0,
        )

        _, parts_dir = self._get_actual_paths(d, log_file)
        _find_parts_file(parts_dir, 'ui', stem='html', ext='.html')
        assert not os.path.exists(os.path.join(parts_dir, 'debug'))


class TestMaxMessageLengthIntegration:
    """End-to-end: LoggerConfig.max_message_length → JsonLogger → parts extraction."""

    def test_long_leaf_extracted_via_max_message_length(self, tmp_path):
        """max_message_length on LoggerConfig triggers leaf extraction in JsonLogger."""
        log_file = str(tmp_path / 'session.jsonl')
        logger = JsonLogger(file_path=log_file, append=True)

        d = ConcreteDebuggable(
            logger={'file': (logger, LoggerConfig(
                max_message_length=100,
                pass_item_key_as='parts_key_path_root',
            ))},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info({'msg': 'short', 'body': 'x' * 300}, 'Data')

        # Find actual file (space handler turns file_path into dir)
        actual_file = os.path.join(log_file, d.id)
        assert os.path.isfile(actual_file)

        with open(actual_file, 'r', encoding='utf-8') as f:
            entry = json.loads(f.readline())

        # Short string stays inline
        assert entry['item']['msg'] == 'short'
        # Long string extracted to parts
        assert isinstance(entry['item']['body'], dict)
        assert '__parts_file__' in entry['item']['body']

    def test_short_strings_stay_inline(self, tmp_path):
        """When all strings are under max_message_length, nothing is extracted."""
        log_file = str(tmp_path / 'session.jsonl')
        logger = JsonLogger(file_path=log_file, append=True)

        d = ConcreteDebuggable(
            logger={'file': (logger, LoggerConfig(max_message_length=1000))},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        d.log_info({'msg': 'hello', 'data': 'world'}, 'Data')

        actual_file = os.path.join(log_file, d.id)
        with open(actual_file, 'r', encoding='utf-8') as f:
            entry = json.loads(f.readline())

        assert entry['item']['msg'] == 'hello'
        assert entry['item']['data'] == 'world'

    def test_per_type_max_applies(self, tmp_path):
        """max_message_length_by_log_type applies to specific log types."""
        log_file = str(tmp_path / 'session.jsonl')
        logger = JsonLogger(file_path=log_file, append=True)

        d = ConcreteDebuggable(
            logger={'file': (logger, LoggerConfig(
                max_message_length_by_log_type={'Data': 50},
                pass_item_key_as='parts_key_path_root',
            ))},
            always_add_logging_based_logger=False,
            log_time=False,
        )
        long_str = 'z' * 200

        # 'Data' type — should trigger extraction
        d.log_info({'content': long_str}, 'Data')
        # 'Error' type — no limit, should stay inline
        d.log_info({'content': long_str}, 'Error')

        actual_file = os.path.join(log_file, d.id)
        with open(actual_file, 'r', encoding='utf-8') as f:
            data_entry = json.loads(f.readline())
            error_entry = json.loads(f.readline())

        # Data entry has extraction
        assert isinstance(data_entry['item']['content'], dict)
        assert '__parts_file__' in data_entry['item']['content']
        # Error entry is inline
        assert error_entry['item']['content'] == long_str
