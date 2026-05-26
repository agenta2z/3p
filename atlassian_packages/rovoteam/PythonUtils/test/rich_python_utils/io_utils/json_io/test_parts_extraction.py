"""
Test write_json's PartsKeyPath features directly (no Debuggable dependency).

Covers: PartsKeyPath class, alias, subfolder, group_by_key,
parts_min_size filtering, and mixed tuple/PartsKeyPath entries.
"""

import glob as _glob
import json
import os

import pytest

from python_utils.io_utils.json_io import (
    write_json, PartsKeyPath, JsonLogger, JsonLogReader,
    iter_json_objs, resolve_json_parts, _resolve_parts_references,
    iter_all_json_objs_from_all_sub_dirs,
)


def _find_parts_file(base_dir, *subdirs, stem, ext):
    """Find a uniquely-named parts file matching the stem and extension.

    Parts files now always use timestamp+uuid naming (e.g.
    ``20260218_143052_AfterHtml_a1b2c3d4.html``).  This helper locates
    the single file whose name contains *stem* and ends with *ext*.
    """
    search_dir = os.path.join(base_dir, *subdirs) if subdirs else base_dir
    pattern = os.path.join(search_dir, f'*{stem}*{ext}')
    matches = _glob.glob(pattern)
    assert len(matches) == 1, (
        f"Expected exactly 1 file matching {pattern}, got {len(matches)}: {matches}"
    )
    return matches[0]


def _make_sample_dict():
    """Sample dict with HTML-like string values for extraction."""
    return {
        'body_html_before': '<html><body><h1>Before</h1><p>Old content here</p></body></html>',
        'body_html_after': '<html><body><h1>After</h1><p>New content here</p></body></html>',
        'cleaned_html': '<div><h1>After</h1><p>New content here</p></div>',
        'source': 'test',
        'count': 42,
    }


class TestPartsKeyPathClass:
    """Test PartsKeyPath as input to write_json's parts_key_paths."""

    def test_alias_used_in_filename(self, tmp_path):
        """PartsKeyPath.alias overrides the key path in the output filename."""
        log_file = str(tmp_path / 'output.json')
        write_json(
            _make_sample_dict(), log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml'),
            ],
            parts_min_size=0,
        )

        _find_parts_file(log_file + '.parts', stem='AfterHtml', ext='.html')

    def test_subfolder_creates_directory(self, tmp_path):
        """PartsKeyPath.subfolder nests the parts file under a subdirectory."""
        log_file = str(tmp_path / 'output.json')
        write_json(
            _make_sample_dict(), log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', subfolder='html_files'),
            ],
            parts_min_size=0,
        )

        _find_parts_file(log_file + '.parts', 'html_files', stem='body_html_after', ext='.html')

    def test_subfolder_and_group_by_key_combined(self, tmp_path):
        """subfolder + parts_group_by_key produces nested directories."""
        log_file = str(tmp_path / 'output.json')
        write_json(
            _make_sample_dict(), log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml', subfolder='ui_source'),
            ],
            parts_min_size=0,
            parts_group_by_key=True,
        )

        _find_parts_file(log_file + '.parts', 'ui_source', 'AfterHtml', stem='AfterHtml', ext='.html')

    def test_parts_min_size_skips_small_values(self, tmp_path):
        """Values smaller than parts_min_size are left inline."""
        log_file = str(tmp_path / 'output.json')
        write_json(
            _make_sample_dict(), log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html'),
            ],
            parts_min_size=999999,
        )

        parts_dir = log_file + '.parts'
        if os.path.isdir(parts_dir):
            file_count = sum(len(f) for _, _, f in os.walk(parts_dir))
            assert file_count == 0

    def test_mixed_tuple_and_parts_key_path(self, tmp_path):
        """PartsKeyPath and plain tuple entries can coexist in the same list."""
        log_file = str(tmp_path / 'output.json')
        write_json(
            _make_sample_dict(), log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_before', ext='.html', alias='BeforeHtml', subfolder='ui_source'),
                ('body_html_after', '.html'),  # plain tuple, no subfolder
            ],
            parts_min_size=0,
        )

        parts_dir = log_file + '.parts'
        _find_parts_file(parts_dir, 'ui_source', stem='BeforeHtml', ext='.html')
        _find_parts_file(parts_dir, stem='body_html_after', ext='.html')

    def test_content_matches_original(self, tmp_path):
        """Extracted parts file content equals the original value."""
        log_file = str(tmp_path / 'output.json')
        data = _make_sample_dict()
        write_json(
            data, log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html'),
            ],
            parts_min_size=0,
        )

        parts_file = _find_parts_file(log_file + '.parts', stem='body_html_after', ext='.html')
        with open(parts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        assert content == data['body_html_after']

    def test_reference_in_main_json(self, tmp_path):
        """Extracted values are replaced with __parts_file__ references."""
        log_file = str(tmp_path / 'output.json')
        write_json(
            _make_sample_dict(), log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml', subfolder='html_files'),
            ],
            parts_min_size=0,
        )

        with open(log_file, 'r', encoding='utf-8') as f:
            result = json.loads(f.readline())

        ref = result['body_html_after']
        assert isinstance(ref, dict)
        assert 'AfterHtml' in ref['__parts_file__'] and ref['__parts_file__'].endswith('.html')
        assert 'html_files' in ref['__parts_file__']
        assert ref['__value_type__'] == 'str'

    def test_non_extracted_fields_remain(self, tmp_path):
        """Fields not in parts_key_paths stay as plain values."""
        log_file = str(tmp_path / 'output.json')
        write_json(
            _make_sample_dict(), log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html'),
            ],
            parts_min_size=0,
        )

        with open(log_file, 'r', encoding='utf-8') as f:
            result = json.loads(f.readline())

        assert result['source'] == 'test'
        assert result['count'] == 42

    def test_repr(self):
        """PartsKeyPath repr shows only non-None fields."""
        p = PartsKeyPath('body_html', ext='.html', subfolder='ui')
        assert repr(p) == "PartsKeyPath('body_html', ext='.html', subfolder='ui')"

        p2 = PartsKeyPath('item')
        assert repr(p2) == "PartsKeyPath('item')"


class TestSubfolderWithParts:
    """Test write_json's subfolder parameter interacting with parts extraction."""

    def test_subfolder_redirects_main_file(self, tmp_path):
        """subfolder inserts a directory between parent and filename."""
        log_file = str(tmp_path / 'session.jsonl')
        write_json(
            _make_sample_dict(), log_file,
            subfolder='iter_0001',
        )

        expected = str(tmp_path / 'iter_0001' / 'session.jsonl')
        assert os.path.isfile(expected)
        assert not os.path.isfile(log_file)

    def test_subfolder_with_parts(self, tmp_path):
        """Parts dir is co-located with the subfolder-redirected main file."""
        log_file = str(tmp_path / 'session.jsonl')
        write_json(
            _make_sample_dict(), log_file,
            subfolder='iter_0001',
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml'),
            ],
            parts_min_size=0,
        )

        main_file = str(tmp_path / 'iter_0001' / 'session.jsonl')
        assert os.path.isfile(main_file)
        _find_parts_file(main_file + '.parts', stem='AfterHtml', ext='.html')

    def test_subfolder_with_parts_content_matches(self, tmp_path):
        """Extracted content is correct when subfolder is used."""
        log_file = str(tmp_path / 'session.jsonl')
        data = _make_sample_dict()
        write_json(
            data, log_file,
            subfolder='iter_0001',
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html'),
            ],
            parts_min_size=0,
        )

        parts_file = _find_parts_file(
            str(tmp_path / 'iter_0001' / 'session.jsonl') + '.parts',
            stem='body_html_after', ext='.html',
        )
        with open(parts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        assert content == data['body_html_after']

    def test_subfolder_with_entry_subfolder(self, tmp_path):
        """write_json subfolder + PartsKeyPath.subfolder both apply."""
        log_file = str(tmp_path / 'session.jsonl')
        write_json(
            _make_sample_dict(), log_file,
            subfolder='iter_0001',
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml', subfolder='ui_source'),
            ],
            parts_min_size=0,
        )

        _find_parts_file(
            str(tmp_path / 'iter_0001' / 'session.jsonl') + '.parts',
            'ui_source', stem='AfterHtml', ext='.html',
        )

    def test_subfolder_with_parts_reference(self, tmp_path):
        """Main JSON reference paths are correct when subfolder is used."""
        log_file = str(tmp_path / 'session.jsonl')
        write_json(
            _make_sample_dict(), log_file,
            subfolder='iter_0001',
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml', subfolder='ui_source'),
            ],
            parts_min_size=0,
        )

        main_file = str(tmp_path / 'iter_0001' / 'session.jsonl')
        with open(main_file, 'r', encoding='utf-8') as f:
            result = json.loads(f.readline())

        ref = result['body_html_after']
        assert ref['__parts_file__'].startswith('ui_source')
        assert 'AfterHtml' in ref['__parts_file__'] and ref['__parts_file__'].endswith('.html')
        assert ref['__value_type__'] == 'str'

    def test_subfolder_with_space_and_parts(self, tmp_path):
        """subfolder + space + parts all compose correctly."""
        log_file = str(tmp_path / 'session.jsonl')
        write_json(
            _make_sample_dict(), log_file,
            subfolder='iter_0001',
            space='agent_01',
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml'),
            ],
            parts_min_size=0,
        )

        # subfolder applied first → iter_0001/session.jsonl
        # space turns file into dir → iter_0001/session.jsonl/agent_01
        space_file = str(tmp_path / 'iter_0001' / 'session.jsonl' / 'agent_01')
        assert os.path.isfile(space_file)
        _find_parts_file(space_file + '.parts', stem='AfterHtml', ext='.html')


class TestJsonLogger:
    """Test JsonLogger as a callable write_json wrapper."""

    def test_basic_write(self, tmp_path):
        """JsonLogger writes JSON the same way as write_json."""
        log_file = str(tmp_path / 'output.json')
        logger = JsonLogger(file_path=log_file)
        logger(_make_sample_dict())

        with open(log_file, 'r', encoding='utf-8') as f:
            result = json.loads(f.readline())
        assert result['source'] == 'test'
        assert result['count'] == 42

    def test_group_maps_to_subfolder(self, tmp_path):
        """group kwarg is mapped to subfolder in write_json."""
        log_file = str(tmp_path / 'session.jsonl')
        logger = JsonLogger(file_path=log_file)
        logger(_make_sample_dict(), group='iter_0001')

        expected = str(tmp_path / 'iter_0001' / 'session.jsonl')
        assert os.path.isfile(expected)
        assert not os.path.isfile(log_file)

    def test_group_with_parts(self, tmp_path):
        """group → subfolder works together with parts extraction."""
        log_file = str(tmp_path / 'session.jsonl')
        logger = JsonLogger(file_path=log_file)
        logger(
            _make_sample_dict(),
            group='iter_0001',
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml'),
            ],
            parts_min_size=0,
        )

        main_file = str(tmp_path / 'iter_0001' / 'session.jsonl')
        assert os.path.isfile(main_file)
        _find_parts_file(main_file + '.parts', stem='AfterHtml', ext='.html')

    def test_explicit_subfolder_takes_precedence(self, tmp_path):
        """If both group and subfolder are passed, subfolder wins."""
        log_file = str(tmp_path / 'session.jsonl')
        logger = JsonLogger(file_path=log_file)
        logger(_make_sample_dict(), group='from_group', subfolder='explicit')

        expected = str(tmp_path / 'explicit' / 'session.jsonl')
        assert os.path.isfile(expected)
        # group is dropped, not used as subfolder
        assert not os.path.isdir(str(tmp_path / 'from_group'))

    def test_file_path_property(self):
        """file_path property is exposed for external discovery."""
        logger = JsonLogger(file_path='logs/session.jsonl', append=True)
        assert logger.file_path == 'logs/session.jsonl'

    def test_keywords_property(self):
        """keywords property returns a copy of baked-in params."""
        logger = JsonLogger(file_path='logs/s.jsonl', append=True)
        kw = logger.keywords
        assert kw == {'file_path': 'logs/s.jsonl', 'append': True}
        # Returns a copy, not the internal dict
        kw['extra'] = True
        assert 'extra' not in logger.keywords

    def test_repr(self):
        """repr shows baked-in params."""
        logger = JsonLogger(file_path='logs/s.jsonl', append=True)
        assert repr(logger) == "JsonLogger(file_path='logs/s.jsonl', append=True)"

    def test_per_call_kwargs_override_baked_in(self, tmp_path):
        """Per-call kwargs override baked-in defaults."""
        log_file = str(tmp_path / 'output.json')
        logger = JsonLogger(file_path=log_file, indent=None)
        logger(_make_sample_dict(), indent=2)

        with open(log_file, 'r', encoding='utf-8') as f:
            raw = f.read()
        # indent=2 means multi-line output
        assert '\n' in raw.strip()


class TestWriteJsonReturnValue:
    """Test that write_json returns the saved dict."""

    def test_returns_original_without_parts(self, tmp_path):
        """Without parts extraction, write_json returns the original dict."""
        log_file = str(tmp_path / 'output.json')
        data = _make_sample_dict()
        result = write_json(data, log_file)
        assert result is data  # Same object, no deep copy needed

    def test_returns_processed_dict_with_parts(self, tmp_path):
        """With parts extraction, write_json returns the deep-copied dict with references."""
        log_file = str(tmp_path / 'output.json')
        data = _make_sample_dict()
        result = write_json(
            data, log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml'),
            ],
            parts_min_size=0,
        )
        # Result is a different object (deep copy)
        assert result is not data
        # Extracted field has __parts_file__ reference
        ref = result['body_html_after']
        assert isinstance(ref, dict)
        assert '__parts_file__' in ref
        assert 'AfterHtml' in ref['__parts_file__'] and ref['__parts_file__'].endswith('.html')
        # Original dict is not mutated
        assert isinstance(data['body_html_after'], str)

    def test_non_extracted_fields_in_return_value(self, tmp_path):
        """Non-extracted fields remain as plain values in the return dict."""
        log_file = str(tmp_path / 'output.json')
        data = _make_sample_dict()
        result = write_json(
            data, log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html'),
            ],
            parts_min_size=0,
        )
        assert result['source'] == 'test'
        assert result['count'] == 42

    def test_json_logger_returns_dict(self, tmp_path):
        """JsonLogger also returns the saved dict via Partial inheritance."""
        log_file = str(tmp_path / 'output.json')
        logger = JsonLogger(file_path=log_file)
        data = _make_sample_dict()
        result = logger(data)
        assert result is data

    def test_json_logger_returns_processed_with_parts(self, tmp_path):
        """JsonLogger returns the processed dict when parts extraction is active."""
        log_file = str(tmp_path / 'output.json')
        logger = JsonLogger(file_path=log_file)
        data = _make_sample_dict()
        result = logger(
            data,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml'),
            ],
            parts_min_size=0,
        )
        assert result is not data
        assert '__parts_file__' in result['body_html_after']


class TestPartsKeyPathRoot:
    """Test write_json's parts_key_path_root parameter."""

    def _make_nested_dict(self):
        """Dict with a nested 'item' key, mimicking Debuggable's log_data."""
        return {
            'type': 'TestType',
            'id': 'test-001',
            'item': _make_sample_dict(),
        }

    def test_root_prefixes_paths(self, tmp_path):
        """parts_key_path_root prefixes paths so they resolve into nested data."""
        log_file = str(tmp_path / 'output.json')
        data = self._make_nested_dict()
        write_json(
            data, log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml'),
            ],
            parts_key_path_root='item',
            parts_min_size=0,
        )

        _find_parts_file(log_file + '.parts', stem='AfterHtml', ext='.html')

    def test_root_file_naming_uses_original_path(self, tmp_path):
        """File stem uses the un-prefixed path, not 'item__body_html_after'."""
        log_file = str(tmp_path / 'output.json')
        write_json(
            self._make_nested_dict(), log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html'),
            ],
            parts_key_path_root='item',
            parts_min_size=0,
        )

        # Without alias, file_stem is 'body_html_after' (not 'item__body_html_after')
        _find_parts_file(log_file + '.parts', stem='body_html_after', ext='.html')

    def test_root_content_matches_nested_value(self, tmp_path):
        """Extracted content equals the nested value."""
        log_file = str(tmp_path / 'output.json')
        data = self._make_nested_dict()
        write_json(
            data, log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html'),
            ],
            parts_key_path_root='item',
            parts_min_size=0,
        )

        parts_file = _find_parts_file(log_file + '.parts', stem='body_html_after', ext='.html')
        with open(parts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        assert content == data['item']['body_html_after']

    def test_root_reference_in_main_json(self, tmp_path):
        """Reference is placed at the prefixed path in the output dict."""
        log_file = str(tmp_path / 'output.json')
        result = write_json(
            self._make_nested_dict(), log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml'),
            ],
            parts_key_path_root='item',
            parts_min_size=0,
        )

        ref = result['item']['body_html_after']
        assert isinstance(ref, dict)
        assert 'AfterHtml' in ref['__parts_file__'] and ref['__parts_file__'].endswith('.html')

    def test_root_none_is_default_no_change(self, tmp_path):
        """parts_key_path_root=None (default) doesn't change behavior."""
        log_file = str(tmp_path / 'output.json')
        write_json(
            _make_sample_dict(), log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml'),
            ],
            parts_key_path_root=None,
            parts_min_size=0,
        )

        _find_parts_file(log_file + '.parts', stem='AfterHtml', ext='.html')

    def test_root_with_subfolder(self, tmp_path):
        """parts_key_path_root works together with PartsKeyPath.subfolder."""
        log_file = str(tmp_path / 'output.json')
        write_json(
            self._make_nested_dict(), log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', alias='AfterHtml', subfolder='ui'),
            ],
            parts_key_path_root='item',
            parts_min_size=0,
        )

        _find_parts_file(log_file + '.parts', 'ui', stem='AfterHtml', ext='.html')


# ---------------------------------------------------------------------------
# artifact_field decorator & get_key_paths_for_artifacts
# ---------------------------------------------------------------------------

from attr import attrs, attrib
from python_utils.io_utils.json_io import artifact_field, get_key_paths_for_artifacts
from python_utils.path_utils.common import resolve_ext


class TestResolveExt:
    """Tests for resolve_ext utility."""

    def test_with_dot(self):
        assert resolve_ext('.html') == '.html'

    def test_without_dot(self):
        assert resolve_ext('html') == '.html'

    def test_none(self):
        assert resolve_ext(None) is None

    def test_empty_string(self):
        assert resolve_ext('') == ''

    def test_custom_sep(self):
        assert resolve_ext('csv', sep='_') == '_csv'
        assert resolve_ext('_csv', sep='_') == '_csv'


class TestArtifactField:
    """Tests for the @artifact_field class decorator."""

    def test_single_artifact(self):
        @artifact_field('body_html', type='html', group='ui_source')
        class MyResult:
            pass

        assert hasattr(MyResult, '__artifacts__')
        assert len(MyResult.__artifacts__) == 1
        entry = MyResult.__artifacts__[0]
        assert isinstance(entry, PartsKeyPath)
        assert entry.key == 'body_html'
        assert entry.ext == '.html'
        assert entry.subfolder == 'ui_source'

    def test_multiple_artifacts(self):
        @artifact_field('field_a', type='html', group='ui')
        @artifact_field('field_b', type='.txt')
        @artifact_field('field_c', alias='FieldC')
        class MyResult:
            pass

        assert len(MyResult.__artifacts__) == 3
        keys = [e.key for e in MyResult.__artifacts__]
        assert 'field_a' in keys
        assert 'field_b' in keys
        assert 'field_c' in keys

    def test_type_normalized_to_ext(self):
        @artifact_field('f', type='json')
        class R:
            pass

        assert R.__artifacts__[0].ext == '.json'

    def test_type_with_dot_preserved(self):
        @artifact_field('f', type='.html')
        class R:
            pass

        assert R.__artifacts__[0].ext == '.html'

    def test_type_none_gives_ext_none(self):
        @artifact_field('f')
        class R:
            pass

        assert R.__artifacts__[0].ext is None

    def test_works_outside_attrs_slots(self):
        """@artifact_field applied outside @attrs(slots=True) preserves metadata."""
        @artifact_field('body', type='html')
        @attrs(slots=True)
        class SlottedResult:
            body: str = attrib(default='')

        assert len(SlottedResult.__artifacts__) == 1
        assert SlottedResult.__artifacts__[0].key == 'body'

        # Also verify the attrs class still works
        obj = SlottedResult(body='<html></html>')
        assert obj.body == '<html></html>'

    def test_no_cross_contamination(self):
        """Each class gets its own __artifacts__ list."""
        @artifact_field('a')
        class A:
            pass

        @artifact_field('b')
        class B:
            pass

        assert len(A.__artifacts__) == 1
        assert A.__artifacts__[0].key == 'a'
        assert len(B.__artifacts__) == 1
        assert B.__artifacts__[0].key == 'b'


class TestGetKeyPathsForArtifacts:
    """Tests for get_key_paths_for_artifacts utility."""

    def test_single_class(self):
        @artifact_field('body', type='html', group='ui')
        class R:
            pass

        paths = get_key_paths_for_artifacts(R)
        assert len(paths) == 1
        assert paths[0].key == 'body'
        assert paths[0].ext == '.html'
        assert paths[0].subfolder == 'ui'

    def test_multiple_classes(self):
        @artifact_field('html', type='html')
        class A:
            pass

        @artifact_field('text', type='txt')
        @artifact_field('data', type='json')
        class B:
            pass

        paths = get_key_paths_for_artifacts(A, B)
        assert len(paths) == 3
        keys = [p.key for p in paths]
        assert keys == ['html', 'data', 'text']

    def test_empty_class(self):
        class NoArtifacts:
            pass

        paths = get_key_paths_for_artifacts(NoArtifacts)
        assert paths == []

    def test_usable_as_parts_key_paths(self, tmp_path):
        """get_key_paths_for_artifacts output works directly in write_json."""
        @artifact_field('body_html', type='html')
        class Result:
            pass

        data = {'body_html': '<html><body>Hello World</body></html>'}
        log_file = str(tmp_path / 'output.json')

        write_json(
            data, log_file,
            parts_key_paths=get_key_paths_for_artifacts(Result),
            parts_min_size=0,
        )

        parts_file = _find_parts_file(log_file + '.parts', stem='body_html', ext='.html')
        with open(parts_file, 'r', encoding='utf-8') as f:
            assert f.read() == data['body_html']


class TestExtNormalizationInWriteJson:
    """Verify write_json handles ext without leading dot."""

    def test_ext_without_dot(self, tmp_path):
        """PartsKeyPath(ext='html') produces .html file."""
        log_file = str(tmp_path / 'output.json')
        data = {'content': '<html><body>Big content for extraction</body></html>'}
        write_json(
            data, log_file,
            parts_key_paths=[PartsKeyPath('content', ext='html')],
            parts_min_size=0,
        )

        _find_parts_file(log_file + '.parts', stem='content', ext='.html')

    def test_ext_with_dot_unchanged(self, tmp_path):
        """PartsKeyPath(ext='.txt') still works as before."""
        log_file = str(tmp_path / 'output.json')
        data = {'content': 'Some large text content for extraction testing'}
        write_json(
            data, log_file,
            parts_key_paths=[PartsKeyPath('content', ext='.txt')],
            parts_min_size=0,
        )

        _find_parts_file(log_file + '.parts', stem='content', ext='.txt')


class TestArtifactsAsParts:
    """Tests for write_json's artifacts_as_parts parameter."""

    def _make_result_class(self):
        @artifact_field('body_html', type='html', group='ui_source')
        @artifact_field('cleaned_html', type='html', group='ui_source')
        @artifact_field('raw_data', type='json', group='debug')
        @attrs(slots=True)
        class Result:
            body_html: str = attrib(default='')
            cleaned_html: str = attrib(default='')
            raw_data: str = attrib(default='')
            status: str = attrib(default='ok')
        return Result

    def test_true_extracts_all_artifacts(self, tmp_path):
        """artifacts_as_parts=True extracts all artifact fields."""
        Result = self._make_result_class()
        obj = Result(
            body_html='<html><body>Before</body></html>',
            cleaned_html='<div>Cleaned</div>',
            raw_data='{"key": "value"}',
        )
        log_file = str(tmp_path / 'output.json')
        write_json(obj, log_file, artifacts_as_parts=True, parts_min_size=0)

        parts_dir = log_file + '.parts'
        _find_parts_file(parts_dir, 'ui_source', stem='body_html', ext='.html')
        _find_parts_file(parts_dir, 'ui_source', stem='cleaned_html', ext='.html')
        _find_parts_file(parts_dir, 'debug', stem='raw_data', ext='.json')

    def test_group_filter(self, tmp_path):
        """artifacts_as_parts=['ui_source'] extracts only that group."""
        Result = self._make_result_class()
        obj = Result(
            body_html='<html><body>Before</body></html>',
            cleaned_html='<div>Cleaned</div>',
            raw_data='{"key": "value"}',
        )
        log_file = str(tmp_path / 'output.json')
        write_json(obj, log_file, artifacts_as_parts=['ui_source'], parts_min_size=0)

        parts_dir = log_file + '.parts'
        _find_parts_file(parts_dir, 'ui_source', stem='body_html', ext='.html')
        _find_parts_file(parts_dir, 'ui_source', stem='cleaned_html', ext='.html')
        assert not os.path.exists(os.path.join(parts_dir, 'debug'))

    def test_merges_with_explicit_parts_key_paths(self, tmp_path):
        """Artifact fields merge with explicit parts_key_paths."""
        Result = self._make_result_class()
        obj = Result(
            body_html='<html><body>Before</body></html>',
            status='this is a long status string for extraction',
        )
        log_file = str(tmp_path / 'output.json')
        write_json(
            obj, log_file,
            artifacts_as_parts=['ui_source'],
            parts_key_paths=[PartsKeyPath('status', ext='.txt')],
            parts_min_size=0,
        )

        parts_dir = log_file + '.parts'
        # Artifact field extracted
        _find_parts_file(parts_dir, 'ui_source', stem='body_html', ext='.html')
        # Explicit parts_key_paths also extracted
        _find_parts_file(parts_dir, stem='status', ext='.txt')

    def test_no_artifacts_is_noop(self, tmp_path):
        """artifacts_as_parts on a class without __artifacts__ does nothing."""
        log_file = str(tmp_path / 'output.json')
        data = {'content': 'hello'}
        write_json(data, log_file, artifacts_as_parts=True, parts_min_size=0)

        # No parts directory created
        assert not os.path.exists(log_file + '.parts')

    def test_content_matches(self, tmp_path):
        """Extracted artifact file content matches the field value."""
        Result = self._make_result_class()
        html = '<html><body>Important content</body></html>'
        obj = Result(body_html=html)
        log_file = str(tmp_path / 'output.json')
        write_json(obj, log_file, artifacts_as_parts=['ui_source'], parts_min_size=0)

        parts_file = _find_parts_file(log_file + '.parts', 'ui_source', stem='body_html', ext='.html')
        with open(parts_file, 'r', encoding='utf-8') as f:
            assert f.read() == html

    def test_explicit_overrides_artifact(self, tmp_path):
        """Explicit parts_key_paths entry for same key takes precedence over artifact."""
        Result = self._make_result_class()
        obj = Result(body_html='<html><body>Content</body></html>')
        log_file = str(tmp_path / 'output.json')
        write_json(
            obj, log_file,
            artifacts_as_parts=True,
            # Override body_html with different ext and no subfolder
            parts_key_paths=[PartsKeyPath('body_html', ext='.txt')],
            parts_min_size=0,
        )

        parts_dir = log_file + '.parts'
        # Explicit entry wins: .txt, no subfolder (not .html in ui_source/)
        _find_parts_file(parts_dir, stem='body_html', ext='.txt')
        # body_html should NOT appear under ui_source/ (the artifact subfolder)
        ui_source_dir = os.path.join(parts_dir, 'ui_source')
        if os.path.isdir(ui_source_dir):
            ui_files = os.listdir(ui_source_dir)
            assert not any('body_html' in f for f in ui_files)


class TestGetKeyPathsForArtifactsGroupFilter:
    """Tests for the groups parameter of get_key_paths_for_artifacts."""

    def test_filter_single_group_string(self):
        @artifact_field('a', type='html', group='ui')
        @artifact_field('b', type='json', group='debug')
        class R:
            pass

        paths = get_key_paths_for_artifacts(R, groups='ui')
        assert len(paths) == 1
        assert paths[0].key == 'a'

    def test_filter_multiple_groups(self):
        @artifact_field('a', type='html', group='ui')
        @artifact_field('b', type='json', group='debug')
        @artifact_field('c', type='txt', group='other')
        class R:
            pass

        paths = get_key_paths_for_artifacts(R, groups=['ui', 'debug'])
        assert len(paths) == 2
        keys = {p.key for p in paths}
        assert keys == {'a', 'b'}

    def test_no_filter_returns_all(self):
        @artifact_field('a', group='ui')
        @artifact_field('b', group='debug')
        class R:
            pass

        paths = get_key_paths_for_artifacts(R)
        assert len(paths) == 2


class TestGetKeyPathsRecursive:
    """Tests for get_key_paths_for_artifacts with recursive=True."""

    def test_discovers_nested_artifacts(self):
        """Nested class artifacts are collected with dotted key prefix."""
        @artifact_field('data', type='json')
        @attrs(slots=True)
        class Inner:
            data: str = attrib(default='')

        @artifact_field('top', type='html')
        @attrs(slots=True)
        class Outer:
            top: str = attrib(default='')
            child: Inner = attrib(factory=Inner)

        paths = get_key_paths_for_artifacts(Outer, recursive=True)
        keys = [p.key for p in paths]
        assert 'top' in keys
        assert 'child.data' in keys
        assert len(paths) == 2

    def test_parent_artifact_skips_child_recursion(self):
        """If parent field is an artifact, child artifacts are not collected."""
        @artifact_field('data', type='json')
        @attrs(slots=True)
        class Inner:
            data: str = attrib(default='')

        @artifact_field('child', type='json')
        @attrs(slots=True)
        class Outer:
            child: Inner = attrib(factory=Inner)

        paths = get_key_paths_for_artifacts(Outer, recursive=True)
        keys = [p.key for p in paths]
        assert keys == ['child']
        # child.data is NOT included because 'child' is already an artifact

    def test_three_levels_deep(self):
        """Recursive discovery works across multiple nesting levels."""
        @artifact_field('leaf', type='txt')
        @attrs(slots=True)
        class L3:
            leaf: str = attrib(default='')

        @attrs(slots=True)
        class L2:
            nested: L3 = attrib(factory=L3)

        @artifact_field('top', type='html')
        @attrs(slots=True)
        class L1:
            top: str = attrib(default='')
            mid: L2 = attrib(factory=L2)

        paths = get_key_paths_for_artifacts(L1, recursive=True)
        keys = [p.key for p in paths]
        assert 'top' in keys
        assert 'mid.nested.leaf' in keys
        assert len(paths) == 2

    def test_recursive_false_does_not_recurse(self):
        """Default recursive=False only returns direct artifacts."""
        @artifact_field('data', type='json')
        @attrs(slots=True)
        class Inner:
            data: str = attrib(default='')

        @artifact_field('top', type='html')
        @attrs(slots=True)
        class Outer:
            top: str = attrib(default='')
            child: Inner = attrib(factory=Inner)

        paths = get_key_paths_for_artifacts(Outer)
        keys = [p.key for p in paths]
        assert keys == ['top']

    def test_recursive_with_groups_filter(self):
        """Groups filter applies after recursive collection."""
        @artifact_field('html_field', type='html', group='ui')
        @attrs(slots=True)
        class InnerUI:
            html_field: str = attrib(default='')

        @artifact_field('debug_data', type='json', group='debug')
        @attrs(slots=True)
        class InnerDebug:
            debug_data: str = attrib(default='')

        @attrs(slots=True)
        class Root:
            ui: InnerUI = attrib(factory=InnerUI)
            dbg: InnerDebug = attrib(factory=InnerDebug)

        paths = get_key_paths_for_artifacts(Root, recursive=True, groups='ui')
        assert len(paths) == 1
        assert paths[0].key == 'ui.html_field'
        assert paths[0].subfolder == 'ui'

    def test_preserves_ext_alias_subfolder(self):
        """Nested artifact entries preserve ext, alias, and subfolder."""
        @artifact_field('content', type='html', alias='PageContent', group='ui')
        @attrs(slots=True)
        class Inner:
            content: str = attrib(default='')

        @attrs(slots=True)
        class Outer:
            child: Inner = attrib(factory=Inner)

        paths = get_key_paths_for_artifacts(Outer, recursive=True)
        assert len(paths) == 1
        entry = paths[0]
        assert entry.key == 'child.content'
        assert entry.ext == '.html'
        assert entry.alias == 'PageContent'
        assert entry.subfolder == 'ui'

    def test_recursive_with_write_json(self, tmp_path):
        """Recursive artifact paths work end-to-end with write_json."""
        @artifact_field('body', type='html')
        @attrs(slots=True)
        class Inner:
            body: str = attrib(default='')

        @attrs(slots=True)
        class Outer:
            child: Inner = attrib(factory=Inner)
            name: str = attrib(default='')

        data = {
            'child': {'body': '<html><body>Large HTML content for extraction</body></html>'},
            'name': 'test',
        }
        log_file = str(tmp_path / 'output.json')
        write_json(
            data, log_file,
            parts_key_paths=get_key_paths_for_artifacts(Outer, recursive=True),
            parts_min_size=0,
        )

        parts_file = _find_parts_file(log_file + '.parts', stem='child__body', ext='.html')
        with open(parts_file, 'r', encoding='utf-8') as f:
            assert f.read() == data['child']['body']


class TestLeafAsPartsIfExceedingSize:
    """Tests for write_json / jsonfy leaf_as_parts_if_exceeding_size parameter."""

    def test_long_string_extracted(self, tmp_path):
        """Leaf string exceeding threshold is extracted to a parts file."""
        log_file = str(tmp_path / 'output.json')
        long_value = 'x' * 200
        data = {'short': 'ok', 'long_field': long_value}
        result = write_json(data, log_file, leaf_as_parts_if_exceeding_size=100)

        # Parts file created with the long string content
        parts_dir = log_file + '.parts'
        assert os.path.isdir(parts_dir)
        _find_parts_file(parts_dir, stem='long_field', ext='.txt')

        # Main JSON has a __parts_file__ reference
        with open(log_file, 'r', encoding='utf-8') as f:
            saved = json.loads(f.readline())
        assert isinstance(saved['long_field'], dict)
        assert '__parts_file__' in saved['long_field']
        # Short field unchanged
        assert saved['short'] == 'ok'

    def test_short_string_stays_inline(self, tmp_path):
        """Leaf string under threshold stays inline."""
        log_file = str(tmp_path / 'output.json')
        data = {'msg': 'hello world'}
        write_json(data, log_file, leaf_as_parts_if_exceeding_size=100)

        with open(log_file, 'r', encoding='utf-8') as f:
            saved = json.loads(f.readline())
        assert saved['msg'] == 'hello world'
        # No parts directory created
        assert not os.path.exists(log_file + '.parts')

    def test_nested_long_string_extracted(self, tmp_path):
        """Nested leaf strings exceeding threshold are extracted."""
        log_file = str(tmp_path / 'output.json')
        data = {
            'level1': {
                'level2': {
                    'big': 'y' * 300,
                    'small': 'tiny',
                },
            },
        }
        write_json(data, log_file, leaf_as_parts_if_exceeding_size=100)

        parts_dir = log_file + '.parts'
        _find_parts_file(parts_dir, stem='level1__level2__big', ext='.txt')

        with open(log_file, 'r', encoding='utf-8') as f:
            saved = json.loads(f.readline())
        assert isinstance(saved['level1']['level2']['big'], dict)
        assert '__parts_file__' in saved['level1']['level2']['big']
        assert saved['level1']['level2']['small'] == 'tiny'

    def test_non_string_leaves_ignored(self, tmp_path):
        """Non-string values (ints, bools, lists) are never extracted."""
        log_file = str(tmp_path / 'output.json')
        data = {'count': 999999, 'flag': True, 'items': [1, 2, 3]}
        write_json(data, log_file, leaf_as_parts_if_exceeding_size=1)

        with open(log_file, 'r', encoding='utf-8') as f:
            saved = json.loads(f.readline())
        assert saved['count'] == 999999
        assert saved['flag'] is True
        assert saved['items'] == [1, 2, 3]
        assert not os.path.exists(log_file + '.parts')

    def test_explicit_parts_key_paths_take_precedence(self, tmp_path):
        """Explicit parts_key_paths extraction runs first; max_leaf doesn't double-extract."""
        log_file = str(tmp_path / 'output.json')
        long_html = '<html>' + 'x' * 300 + '</html>'
        data = {'body_html': long_html, 'other': 'z' * 200}
        write_json(
            data, log_file,
            parts_key_paths=[PartsKeyPath('body_html', ext='.html')],
            parts_min_size=0,
            leaf_as_parts_if_exceeding_size=100,
        )

        parts_dir = log_file + '.parts'
        # body_html extracted by explicit parts_key_paths (with .html ext)
        _find_parts_file(parts_dir, stem='body_html', ext='.html')
        # other extracted by leaf_as_parts_if_exceeding_size (auto-detected .txt)
        _find_parts_file(parts_dir, stem='other', ext='.txt')

    def test_none_disables(self, tmp_path):
        """leaf_as_parts_if_exceeding_size=None (default) does no auto-extraction."""
        log_file = str(tmp_path / 'output.json')
        data = {'big': 'a' * 10000}
        write_json(data, log_file, leaf_as_parts_if_exceeding_size=None)

        with open(log_file, 'r', encoding='utf-8') as f:
            saved = json.loads(f.readline())
        assert saved['big'] == 'a' * 10000
        assert not os.path.exists(log_file + '.parts')

    def test_extracted_content_matches_original(self, tmp_path):
        """Extracted parts file content equals the original string value."""
        log_file = str(tmp_path / 'output.json')
        original = 'Hello World! ' * 50
        data = {'content': original}
        write_json(data, log_file, leaf_as_parts_if_exceeding_size=100)

        parts_file = _find_parts_file(log_file + '.parts', stem='content', ext='.txt')
        with open(parts_file, 'r', encoding='utf-8') as f:
            assert f.read() == original


# ---------------------------------------------------------------------------
# is_artifact shorthand & wildcard expansion for scalars
# ---------------------------------------------------------------------------

class TestIsArtifact:
    """Test ``is_artifact`` convenience parameter and '*' wildcard with scalar root values."""

    def test_is_artifact_extracts_all_top_level_keys(self, tmp_path):
        """is_artifact=True extracts all top-level string values."""
        log_file = str(tmp_path / 'output.json')
        data = {
            'body': '<html><body>Hello</body></html>',
            'notes': 'Some notes here for testing',
            'count': 42,
        }
        write_json(data, log_file, is_artifact=True, parts_min_size=0)

        parts_dir = log_file + '.parts'
        assert os.path.isdir(parts_dir)
        _find_parts_file(parts_dir, stem='body', ext='.html')
        _find_parts_file(parts_dir, stem='notes', ext='.txt')

    def test_is_artifact_with_root_extracts_nested_dict_fields(self, tmp_path):
        """is_artifact=True with parts_key_path_root expands nested dict's keys."""
        log_file = str(tmp_path / 'output.json')
        data = {
            'type': 'TestType',
            'item': {
                'body_html': '<html><body>Content</body></html>',
                'summary': 'A summary',
            },
        }
        write_json(
            data, log_file,
            is_artifact=True,
            parts_key_path_root='item',
            parts_min_size=0,
        )

        parts_dir = log_file + '.parts'
        assert os.path.isdir(parts_dir)
        _find_parts_file(parts_dir, stem='body_html', ext='.html')
        _find_parts_file(parts_dir, stem='summary', ext='.txt')

    def test_is_artifact_with_root_scalar_string(self, tmp_path):
        """is_artifact=True with scalar string at root extracts the string itself."""
        log_file = str(tmp_path / 'output.json')
        prompt_text = 'You are an agent. Please do the following task...'
        data = {
            'type': 'ReasonerInput',
            'id': 'agent-001',
            'item': prompt_text,
        }
        write_json(
            data, log_file,
            is_artifact=True,
            parts_key_path_root='item',
            parts_min_size=0,
        )

        parts_dir = log_file + '.parts'
        assert os.path.isdir(parts_dir)
        # 'item' stem is suppressed in file naming — look for any .txt file
        txt_files = _glob.glob(os.path.join(parts_dir, '*.txt'))
        assert len(txt_files) == 1
        with open(txt_files[0], 'r', encoding='utf-8') as f:
            assert f.read() == prompt_text

    def test_is_artifact_with_root_scalar_html(self, tmp_path):
        """Scalar HTML string at root gets extracted with .html extension."""
        log_file = str(tmp_path / 'output.json')
        html_content = '<html><body><h1>Page</h1></body></html>'
        data = {
            'type': 'Screenshot',
            'item': html_content,
        }
        write_json(
            data, log_file,
            is_artifact=True,
            parts_key_path_root='item',
            parts_min_size=0,
        )

        parts_dir = log_file + '.parts'
        html_files = _glob.glob(os.path.join(parts_dir, '*.html'))
        assert len(html_files) == 1
        with open(html_files[0], 'r', encoding='utf-8') as f:
            assert f.read() == html_content

    def test_is_artifact_reference_replaces_value(self, tmp_path):
        """Scalar at root is replaced with a __parts_file__ reference."""
        log_file = str(tmp_path / 'output.json')
        data = {
            'type': 'ReasonerInput',
            'item': 'Some long prompt text for the agent',
        }
        result = write_json(
            data, log_file,
            is_artifact=True,
            parts_key_path_root='item',
            parts_min_size=0,
        )

        ref = result['item']
        assert isinstance(ref, dict)
        assert '__parts_file__' in ref
        assert ref['__value_type__'] == 'str'

    def test_is_artifact_false_no_extraction(self, tmp_path):
        """is_artifact=False (default) does not trigger extraction."""
        log_file = str(tmp_path / 'output.json')
        data = {'content': 'x' * 1000}
        write_json(data, log_file, is_artifact=False)

        assert not os.path.exists(log_file + '.parts')

    def test_is_artifact_does_not_override_explicit_parts_key_paths(self, tmp_path):
        """is_artifact=True is ignored when parts_key_paths is already set."""
        log_file = str(tmp_path / 'output.json')
        data = {'body': '<html>content</html>', 'notes': 'extra notes'}
        write_json(
            data, log_file,
            is_artifact=True,
            parts_key_paths=[PartsKeyPath('body', ext='.html')],
            parts_min_size=0,
        )

        parts_dir = log_file + '.parts'
        # Only 'body' should be extracted (explicit parts_key_paths takes precedence)
        _find_parts_file(parts_dir, stem='body', ext='.html')
        # 'notes' should NOT be extracted
        txt_files = _glob.glob(os.path.join(parts_dir, '*notes*'))
        assert len(txt_files) == 0

    def test_is_artifact_type_tuple_match(self, tmp_path):
        """is_artifact=(str,) extracts when content at root is a string."""
        log_file = str(tmp_path / 'output.json')
        data = {
            'type': 'ReasonerResponse',
            'item': 'Raw LLM text response here',
        }
        write_json(
            data, log_file,
            is_artifact=(str,),
            parts_key_path_root='item',
            parts_min_size=0,
        )

        parts_dir = log_file + '.parts'
        assert os.path.isdir(parts_dir)
        txt_files = _glob.glob(os.path.join(parts_dir, '*.txt'))
        assert len(txt_files) == 1

    def test_is_artifact_type_tuple_no_match(self, tmp_path):
        """is_artifact=(str,) does NOT extract when content is a dict."""
        log_file = str(tmp_path / 'output.json')
        data = {
            'type': 'ReasonerResponse',
            'item': {'parsed': 'structured data', 'score': 0.9},
        }
        write_json(
            data, log_file,
            is_artifact=(str,),
            parts_key_path_root='item',
            parts_min_size=0,
        )

        assert not os.path.exists(log_file + '.parts')

    def test_is_artifact_type_tuple_multiple_types(self, tmp_path):
        """is_artifact=(str, list) matches either type."""
        log_file = str(tmp_path / 'output.json')
        data = {
            'type': 'Test',
            'item': ['item1', 'item2', 'item3'],
        }
        write_json(
            data, log_file,
            is_artifact=(str, list),
            parts_key_path_root='item',
            parts_min_size=0,
        )

        parts_dir = log_file + '.parts'
        assert os.path.isdir(parts_dir)

    def test_is_artifact_type_tuple_no_root(self, tmp_path):
        """is_artifact=(dict,) without root checks obj itself."""
        log_file = str(tmp_path / 'output.json')
        data = {'body': 'hello world', 'count': 5}
        write_json(
            data, log_file,
            is_artifact=(dict,),
            parts_min_size=0,
        )

        parts_dir = log_file + '.parts'
        assert os.path.isdir(parts_dir)

    def test_is_artifact_type_tuple_no_root_no_match(self, tmp_path):
        """is_artifact=(str,) without root — obj is a dict, no match."""
        log_file = str(tmp_path / 'output.json')
        data = {'body': 'hello world'}
        write_json(
            data, log_file,
            is_artifact=(str,),
            parts_min_size=0,
        )

        assert not os.path.exists(log_file + '.parts')

    def test_wildcard_with_root_none_value(self, tmp_path):
        """'*' with root pointing to None results in no extraction."""
        log_file = str(tmp_path / 'output.json')
        data = {'type': 'Test', 'item': None}
        write_json(
            data, log_file,
            parts_key_paths='*',
            parts_key_path_root='item',
            parts_min_size=0,
        )

        assert not os.path.exists(log_file + '.parts')


# ---------------------------------------------------------------------------
# Tests for is_artifact bypass of parts_min_size
# ---------------------------------------------------------------------------

class TestIsArtifactBypassesPartsMinSize:
    """is_artifact=True should extract values regardless of parts_min_size."""

    def test_artifact_bypasses_parts_min_size(self, tmp_path):
        """is_artifact=True extracts small values even with a high parts_min_size."""
        log_file = str(tmp_path / 'output.json')
        data = {'content': 'short', 'meta': 'x'}
        write_json(
            data, log_file,
            is_artifact=True,
            parts_min_size=999999,
        )

        parts_dir = log_file + '.parts'
        assert os.path.isdir(parts_dir)
        all_files = []
        for _, _, files in os.walk(parts_dir):
            all_files.extend(files)
        assert len(all_files) >= 1, f"Expected parts files, got none in {parts_dir}"

    def test_non_artifact_respects_parts_min_size(self, tmp_path):
        """is_artifact=False still obeys parts_min_size — small values stay inline."""
        log_file = str(tmp_path / 'output.json')
        data = {'content': 'short', 'meta': 'x'}
        write_json(
            data, log_file,
            is_artifact=False,
            parts_key_paths='*',
            parts_min_size=999999,
        )

        parts_dir = log_file + '.parts'
        if os.path.isdir(parts_dir):
            file_count = sum(len(f) for _, _, f in os.walk(parts_dir))
            assert file_count == 0

    def test_artifact_bypass_with_parts_key_path_root(self, tmp_path):
        """Bypass works with parts_key_path_root (the inferencer logging pattern)."""
        log_file = str(tmp_path / 'output.json')
        data = {
            'type': 'InferenceInput',
            'item': 'tiny prompt',
            'level': 20,
            'name': 'TestInferencer',
        }
        write_json(
            data, log_file,
            is_artifact=True,
            parts_key_path_root='item',
            parts_min_size=999999,
        )

        parts_dir = log_file + '.parts'
        assert os.path.isdir(parts_dir)
        all_files = []
        for _, _, files in os.walk(parts_dir):
            all_files.extend(files)
        assert len(all_files) >= 1

    def test_artifact_bypass_dict_item(self, tmp_path):
        """Bypass extracts dict sub-fields when item is a dict."""
        log_file = str(tmp_path / 'output.json')
        data = {
            'type': 'InferenceResponse',
            'item': {'success': True, 'return_code': 0, 'output': 'ok'},
        }
        write_json(
            data, log_file,
            is_artifact=True,
            parts_key_path_root='item',
            parts_min_size=999999,
        )

        parts_dir = log_file + '.parts'
        assert os.path.isdir(parts_dir)
        all_files = []
        for _, _, files in os.walk(parts_dir):
            all_files.extend(files)
        assert len(all_files) == 3, f"Expected 3 parts files (success, return_code, output), got {len(all_files)}"

    def test_artifact_tuple_type_match_bypasses(self, tmp_path):
        """is_artifact as tuple of types bypasses parts_min_size when content matches."""
        log_file = str(tmp_path / 'output.json')
        data = {'type': 'Test', 'item': 'short string'}
        write_json(
            data, log_file,
            is_artifact=(str,),
            parts_key_path_root='item',
            parts_min_size=999999,
        )

        parts_dir = log_file + '.parts'
        assert os.path.isdir(parts_dir)
        all_files = []
        for _, _, files in os.walk(parts_dir):
            all_files.extend(files)
        assert len(all_files) >= 1

    def test_artifact_tuple_type_no_match_no_bypass(self, tmp_path):
        """is_artifact tuple that doesn't match content type produces no extraction."""
        log_file = str(tmp_path / 'output.json')
        data = {'type': 'Test', 'item': {'key': 'value'}}
        write_json(
            data, log_file,
            is_artifact=(str,),
            parts_key_path_root='item',
            parts_min_size=999999,
        )

        parts_dir = log_file + '.parts'
        if os.path.isdir(parts_dir):
            file_count = sum(len(f) for _, _, f in os.walk(parts_dir))
            assert file_count == 0

    def test_artifacts_as_parts_does_not_bypass(self, tmp_path):
        """artifacts_as_parts should NOT bypass parts_min_size (only is_artifact does)."""
        from python_utils.io_utils.json_io import artifact_field

        @artifact_field('content', type='txt')
        class _ArtifactObj:
            def __init__(self):
                self.content = 'tiny'

        log_file = str(tmp_path / 'output.json')
        write_json(
            _ArtifactObj(), log_file,
            artifacts_as_parts=True,
            parts_min_size=999999,
        )

        parts_dir = log_file + '.parts'
        if os.path.isdir(parts_dir):
            file_count = sum(len(f) for _, _, f in os.walk(parts_dir))
            assert file_count == 0

    def test_empty_dict_artifact_no_crash(self, tmp_path):
        """is_artifact=True with empty dict produces zero parts files, no crash."""
        log_file = str(tmp_path / 'output.json')
        write_json(
            {}, log_file,
            is_artifact=True,
            parts_min_size=999999,
        )

        parts_dir = log_file + '.parts'
        if os.path.isdir(parts_dir):
            file_count = sum(len(f) for _, _, f in os.walk(parts_dir))
            assert file_count == 0

    def test_artifact_bypass_round_trip(self, tmp_path):
        """Tiny values extracted via bypass survive round-trip with resolve_parts."""
        log_file = str(tmp_path / 'output.jsonl')
        data = {'status': True, 'code': 0, 'msg': 'ok'}
        write_json(
            data, log_file,
            is_artifact=True,
            parts_min_size=999999,
            append=True,
        )

        results = list(iter_json_objs(log_file, resolve_parts=True))
        assert len(results) == 1
        restored = results[0]
        assert restored['status'] is True
        assert restored['code'] == 0
        assert restored['msg'] == 'ok'


# ---------------------------------------------------------------------------
# Tests for parts resolution (read side)
# ---------------------------------------------------------------------------

class TestResolvePartsReferences:
    """Unit tests for the low-level _resolve_parts_references() function."""

    def test_resolves_str_reference(self, tmp_path):
        parts_dir = str(tmp_path)
        (tmp_path / 'hello.txt').write_text('Hello, World!', encoding='utf-8')
        obj = {'__parts_file__': 'hello.txt', '__value_type__': 'str'}
        result = _resolve_parts_references(obj, parts_dir)
        assert result == 'Hello, World!'

    def test_resolves_json_reference(self, tmp_path):
        parts_dir = str(tmp_path)
        (tmp_path / 'data.json').write_text('{"key": "value"}', encoding='utf-8')
        obj = {'__parts_file__': 'data.json', '__value_type__': 'json'}
        result = _resolve_parts_references(obj, parts_dir)
        assert result == {'key': 'value'}

    def test_resolves_nested_reference(self, tmp_path):
        parts_dir = str(tmp_path)
        (tmp_path / 'hello.txt').write_text('Hello, World!', encoding='utf-8')
        obj = {
            'a': {'__parts_file__': 'hello.txt', '__value_type__': 'str'},
            'b': 42,
        }
        result = _resolve_parts_references(obj, parts_dir)
        assert result == {'a': 'Hello, World!', 'b': 42}

    def test_resolves_reference_in_list(self, tmp_path):
        parts_dir = str(tmp_path)
        (tmp_path / 'hello.txt').write_text('Hello, World!', encoding='utf-8')
        obj = [{'__parts_file__': 'hello.txt', '__value_type__': 'str'}, 'plain']
        result = _resolve_parts_references(obj, parts_dir)
        assert result == ['Hello, World!', 'plain']

    def test_missing_parts_file_returns_marker_unchanged(self, tmp_path):
        parts_dir = str(tmp_path)
        obj = {'__parts_file__': 'nonexistent.txt', '__value_type__': 'str'}
        result = _resolve_parts_references(obj, parts_dir)
        assert result == obj

    def test_plain_dict_passes_through(self, tmp_path):
        parts_dir = str(tmp_path)
        obj = {'a': 1, 'b': 'text'}
        result = _resolve_parts_references(obj, parts_dir)
        assert result == {'a': 1, 'b': 'text'}

    def test_dict_with_extra_keys_not_treated_as_reference(self, tmp_path):
        """Dicts with 3+ keys should not be treated as reference markers."""
        parts_dir = str(tmp_path)
        (tmp_path / 'hello.txt').write_text('Hello, World!', encoding='utf-8')
        obj = {'__parts_file__': 'hello.txt', '__value_type__': 'str', 'extra': True}
        result = _resolve_parts_references(obj, parts_dir)
        assert result == obj

    def test_resolves_reference_in_subdirectory(self, tmp_path):
        parts_dir = str(tmp_path)
        subdir = tmp_path / 'subdir'
        subdir.mkdir()
        (subdir / 'content.html').write_text('<h1>Hello</h1>', encoding='utf-8')
        obj = {'__parts_file__': 'subdir/content.html', '__value_type__': 'str'}
        result = _resolve_parts_references(obj, parts_dir)
        assert result == '<h1>Hello</h1>'


class TestResolveJsonParts:
    """Tests for the public resolve_json_parts() function."""

    def test_resolves_reference_from_source_path(self, tmp_path):
        source_file = str(tmp_path / 'data.json')
        parts_dir = tmp_path / 'data.json.parts'
        parts_dir.mkdir()
        (parts_dir / 'body.txt').write_text('full content', encoding='utf-8')
        obj = {'body': {'__parts_file__': 'body.txt', '__value_type__': 'str'}, 'id': 1}
        result = resolve_json_parts(obj, source_file)
        assert result == {'body': 'full content', 'id': 1}

    def test_returns_unchanged_when_no_parts_dir(self, tmp_path):
        source_file = str(tmp_path / 'data.json')
        obj = {'body': {'__parts_file__': 'body.txt', '__value_type__': 'str'}, 'id': 1}
        result = resolve_json_parts(obj, source_file)
        assert result == obj

    def test_returns_unchanged_for_non_dict(self, tmp_path):
        source_file = str(tmp_path / 'data.json')
        result = resolve_json_parts([1, 2, 3], source_file)
        assert result == [1, 2, 3]

    def test_returns_unchanged_for_none_source_path(self, tmp_path):
        obj = {'body': {'__parts_file__': 'body.txt', '__value_type__': 'str'}}
        result = resolve_json_parts(obj, None)
        assert result == obj

    def test_custom_parts_suffix(self, tmp_path):
        source_file = str(tmp_path / 'data.json')
        parts_dir = tmp_path / 'data.json.extra'
        parts_dir.mkdir()
        (parts_dir / 'body.txt').write_text('custom suffix content', encoding='utf-8')
        obj = {'body': {'__parts_file__': 'body.txt', '__value_type__': 'str'}}
        result = resolve_json_parts(obj, source_file, parts_suffix='.extra')
        assert result == {'body': 'custom suffix content'}


class TestRoundTripPartsResolution:
    """End-to-end round-trip tests: write with parts, read back with resolve_parts=True."""

    def test_basic_round_trip(self, tmp_path):
        log_file = str(tmp_path / 'output.json')
        data = _make_sample_dict()
        write_json(
            data, log_file,
            parts_key_paths=[PartsKeyPath('body_html_before', ext='.html')],
            parts_min_size=0,
        )
        results = list(iter_json_objs(log_file, resolve_parts=True))
        assert len(results) == 1
        assert results[0]['body_html_before'] == data['body_html_before']
        assert results[0]['source'] == 'test'
        assert results[0]['count'] == 42

    def test_round_trip_multiple_fields(self, tmp_path):
        log_file = str(tmp_path / 'output.json')
        data = _make_sample_dict()
        write_json(
            data, log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_before', ext='.html'),
                PartsKeyPath('body_html_after', ext='.html'),
                PartsKeyPath('cleaned_html', ext='.html'),
            ],
            parts_min_size=0,
        )
        results = list(iter_json_objs(log_file, resolve_parts=True))
        assert len(results) == 1
        assert results[0]['body_html_before'] == data['body_html_before']
        assert results[0]['body_html_after'] == data['body_html_after']
        assert results[0]['cleaned_html'] == data['cleaned_html']

    def test_round_trip_with_subfolder(self, tmp_path):
        log_file = str(tmp_path / 'output.json')
        data = _make_sample_dict()
        write_json(
            data, log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html', subfolder='html_files'),
            ],
            parts_min_size=0,
        )
        results = list(iter_json_objs(log_file, resolve_parts=True))
        assert len(results) == 1
        assert results[0]['body_html_after'] == data['body_html_after']

    def test_round_trip_with_group_by_key(self, tmp_path):
        log_file = str(tmp_path / 'output.json')
        data = _make_sample_dict()
        write_json(
            data, log_file,
            parts_key_paths=[
                PartsKeyPath('body_html_after', ext='.html'),
            ],
            parts_group_by_key=True,
            parts_min_size=0,
        )
        results = list(iter_json_objs(log_file, resolve_parts=True))
        assert len(results) == 1
        assert results[0]['body_html_after'] == data['body_html_after']

    def test_round_trip_json_value_type(self, tmp_path):
        log_file = str(tmp_path / 'output.json')
        data = {'nested_data': {'key': [1, 2, 3]}, 'label': 'test'}
        write_json(
            data, log_file,
            parts_key_paths=[PartsKeyPath('nested_data', ext='.json')],
            parts_min_size=0,
        )
        results = list(iter_json_objs(log_file, resolve_parts=True))
        assert len(results) == 1
        assert results[0]['nested_data'] == {'key': [1, 2, 3]}
        assert results[0]['label'] == 'test'

    def test_round_trip_with_parts_key_path_root(self, tmp_path):
        log_file = str(tmp_path / 'output.json')
        data = {
            'type': 'result',
            'item': {
                'body_html': '<html><body>Content</body></html>',
                'title': 'Test',
            },
        }
        write_json(
            data, log_file,
            parts_key_paths=[PartsKeyPath('body_html', ext='.html')],
            parts_key_path_root='item',
            parts_min_size=0,
        )
        results = list(iter_json_objs(log_file, resolve_parts=True))
        assert len(results) == 1
        assert results[0]['item']['body_html'] == data['item']['body_html']
        assert results[0]['type'] == 'result'

    def test_round_trip_leaf_as_parts_if_exceeding_size(self, tmp_path):
        log_file = str(tmp_path / 'output.json')
        long_content = 'x' * 500
        data = {'content': long_content, 'id': 1}
        write_json(
            data, log_file,
            leaf_as_parts_if_exceeding_size=100,
        )
        results = list(iter_json_objs(log_file, resolve_parts=True))
        assert len(results) == 1
        assert results[0]['content'] == long_content
        assert results[0]['id'] == 1

    def test_resolve_parts_false_preserves_references(self, tmp_path):
        log_file = str(tmp_path / 'output.json')
        data = _make_sample_dict()
        write_json(
            data, log_file,
            parts_key_paths=[PartsKeyPath('body_html_before', ext='.html')],
            parts_min_size=0,
        )
        results = list(iter_json_objs(log_file, resolve_parts=False))
        assert len(results) == 1
        ref = results[0]['body_html_before']
        assert isinstance(ref, dict)
        assert '__parts_file__' in ref
        assert '__value_type__' in ref

    def test_round_trip_multiple_json_objects(self, tmp_path):
        log_file = str(tmp_path / 'output.json')
        data1 = {'body': '<html>First</html>', 'id': 1}
        data2 = {'body': '<html>Second</html>', 'id': 2}
        write_json(
            data1, log_file,
            parts_key_paths=[PartsKeyPath('body', ext='.html')],
            parts_min_size=0,
        )
        write_json(
            data2, log_file,
            append=True,
            parts_key_paths=[PartsKeyPath('body', ext='.html')],
            parts_min_size=0,
        )
        results = list(iter_json_objs(log_file, resolve_parts=True))
        assert len(results) == 2
        assert results[0]['body'] == '<html>First</html>'
        assert results[0]['id'] == 1
        assert results[1]['body'] == '<html>Second</html>'
        assert results[1]['id'] == 2

    def test_round_trip_from_directory(self, tmp_path):
        data1 = {'body': '<html>File1</html>', 'id': 1}
        data2 = {'body': '<html>File2</html>', 'id': 2}
        write_json(
            data1, str(tmp_path / 'a.json'),
            parts_key_paths=[PartsKeyPath('body', ext='.html')],
            parts_min_size=0,
        )
        write_json(
            data2, str(tmp_path / 'b.json'),
            parts_key_paths=[PartsKeyPath('body', ext='.html')],
            parts_min_size=0,
        )
        results = list(iter_json_objs(str(tmp_path), resolve_parts=True))
        assert len(results) == 2
        bodies = {r['id']: r['body'] for r in results}
        assert bodies[1] == '<html>File1</html>'
        assert bodies[2] == '<html>File2</html>'

    def test_non_extracted_fields_unchanged(self, tmp_path):
        log_file = str(tmp_path / 'output.json')
        data = _make_sample_dict()
        write_json(
            data, log_file,
            parts_key_paths=[PartsKeyPath('body_html_before', ext='.html')],
            parts_min_size=0,
        )
        results = list(iter_json_objs(log_file, resolve_parts=True))
        assert results[0]['source'] == 'test'
        assert results[0]['count'] == 42
        assert results[0]['body_html_after'] == data['body_html_after']
        assert results[0]['cleaned_html'] == data['cleaned_html']


class TestRoundTripFromSubDirs:
    """Tests for iter_all_json_objs_from_all_sub_dirs with resolve_parts=True."""

    def test_round_trip_from_sub_dirs(self, tmp_path):
        sub1 = tmp_path / 'sub1'
        sub2 = tmp_path / 'sub2'
        sub1.mkdir()
        sub2.mkdir()
        data1 = {'body': '<html>Sub1</html>', 'id': 1}
        data2 = {'body': '<html>Sub2</html>', 'id': 2}
        write_json(
            data1, str(sub1 / 'data.json'),
            parts_key_paths=[PartsKeyPath('body', ext='.html')],
            parts_min_size=0,
        )
        write_json(
            data2, str(sub2 / 'data.json'),
            parts_key_paths=[PartsKeyPath('body', ext='.html')],
            parts_min_size=0,
        )
        results = list(iter_all_json_objs_from_all_sub_dirs(
            str(tmp_path), resolve_parts=True
        ))
        assert len(results) == 2
        bodies = {r['id']: r['body'] for r in results}
        assert bodies[1] == '<html>Sub1</html>'
        assert bodies[2] == '<html>Sub2</html>'

    def test_round_trip_from_multiple_paths(self, tmp_path):
        dir1 = tmp_path / 'dir1'
        dir2 = tmp_path / 'dir2'
        dir1.mkdir()
        dir2.mkdir()
        data1 = {'body': '<html>Dir1</html>', 'id': 1}
        data2 = {'body': '<html>Dir2</html>', 'id': 2}
        write_json(
            data1, str(dir1 / 'data.json'),
            parts_key_paths=[PartsKeyPath('body', ext='.html')],
            parts_min_size=0,
        )
        write_json(
            data2, str(dir2 / 'data.json'),
            parts_key_paths=[PartsKeyPath('body', ext='.html')],
            parts_min_size=0,
        )
        results = list(iter_all_json_objs_from_all_sub_dirs(
            [str(dir1), str(dir2)], resolve_parts=True
        ))
        assert len(results) == 2
        bodies = {r['id']: r['body'] for r in results}
        assert bodies[1] == '<html>Dir1</html>'
        assert bodies[2] == '<html>Dir2</html>'


class TestJsonLogReader:
    """Tests for JsonLogReader — read-side counterpart to JsonLogger."""

    def test_basic_iteration(self, tmp_path):
        """Write JSONL entries, read back with JsonLogReader."""
        log_file = str(tmp_path / 'log.jsonl')
        entries = [
            {'type': 'Info', 'message': 'hello'},
            {'type': 'Debug', 'message': 'world'},
        ]
        for entry in entries:
            write_json(entry, log_file, append=True)

        reader = JsonLogReader(file_path=log_file)
        result = list(reader)
        assert len(result) == 2
        assert result[0]['message'] == 'hello'
        assert result[1]['message'] == 'world'

    def test_resolve_parts_true_by_default(self, tmp_path):
        """Default resolve_parts=True resolves parts references."""
        log_file = str(tmp_path / 'log.jsonl')
        data = {'type': 'Report', 'body': '<html>Full report content here</html>'}
        write_json(
            data, log_file, append=True,
            parts_key_paths=[PartsKeyPath('body', ext='.html')],
            parts_min_size=0,
        )

        reader = JsonLogReader(file_path=log_file)
        result = list(reader)
        assert len(result) == 1
        assert result[0]['body'] == '<html>Full report content here</html>'

    def test_resolve_parts_false_preserves_markers(self, tmp_path):
        """resolve_parts=False preserves reference markers."""
        log_file = str(tmp_path / 'log.jsonl')
        data = {'type': 'Report', 'body': '<html>Content</html>'}
        write_json(
            data, log_file, append=True,
            parts_key_paths=[PartsKeyPath('body', ext='.html')],
            parts_min_size=0,
        )

        reader = JsonLogReader(file_path=log_file, resolve_parts=False)
        result = list(reader)
        assert len(result) == 1
        assert '__parts_file__' in result[0]['body']
        assert '__value_type__' in result[0]['body']

    def test_file_path_property(self, tmp_path):
        """file_path property returns the path passed to constructor."""
        log_file = str(tmp_path / 'log.jsonl')
        reader = JsonLogReader(file_path=log_file)
        assert reader.file_path == log_file

    def test_re_iterable(self, tmp_path):
        """Reader can be iterated multiple times (fresh iterator each time)."""
        log_file = str(tmp_path / 'log.jsonl')
        for i in range(3):
            write_json({'idx': i}, log_file, append=True)

        reader = JsonLogReader(file_path=log_file)
        first_pass = list(reader)
        second_pass = list(reader)
        assert first_pass == second_pass
        assert len(first_pass) == 3

    def test_selection_parameter(self, tmp_path):
        """selection parameter filters fields."""
        log_file = str(tmp_path / 'log.jsonl')
        write_json({'type': 'Info', 'msg': 'hi', 'extra': 42}, log_file, append=True)

        reader = JsonLogReader(file_path=log_file, selection='msg')
        result = list(reader)
        assert len(result) == 1
        assert result[0] == {'msg': 'hi'}

    def test_top_parameter(self, tmp_path):
        """top parameter limits number of results."""
        log_file = str(tmp_path / 'log.jsonl')
        for i in range(10):
            write_json({'idx': i}, log_file, append=True)

        reader = JsonLogReader(file_path=log_file, top=3)
        result = list(reader)
        assert len(result) == 3

    def test_repr(self, tmp_path):
        """__repr__ shows meaningful parameters."""
        log_file = str(tmp_path / 'log.jsonl')
        reader = JsonLogReader(file_path=log_file)
        r = repr(reader)
        assert 'JsonLogReader(' in r
        assert 'file_path=' in r
        assert 'log.jsonl' in r
