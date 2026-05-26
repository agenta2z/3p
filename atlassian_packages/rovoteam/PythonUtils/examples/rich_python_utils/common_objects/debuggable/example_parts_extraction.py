"""
Example: Parts Extraction via Debuggable + write_json

Demonstrates how Debuggable.log_info forwards PartsKeyPath entries
to write_json, which extracts large values (e.g. HTML bodies) into
separate .parts/ files.

This mirrors real usage in WebAgent's web_driver.py, where
WebDriverActionResult HTML fields are extracted into .parts/ files
to keep the main log JSON small and readable.

Output structure (examine the _output/ folder after running):

    _output/
      actions.jsonl/
        {debuggable_id}              <- main JSON (HTML fields replaced with references)
        {debuggable_id}.parts/
          ui_source/                 <- subfolder from PartsKeyPath
            BeforeHtml.html          <- alias from PartsKeyPath
            AfterHtml.html
            CleanedHtml.html

Run:
    cd examples/python_utils/common_objects/debuggable
    python example_parts_extraction.py
"""

import json
import os
import shutil
import sys
from functools import partial
from pathlib import Path

# Resolve src path: walk up from this file to find 'examples', then add sibling 'src'
_current = Path(__file__).resolve()
while _current != _current.parent:
    if _current.name == 'examples':
        sys.path.insert(0, str(_current.parent / 'src'))
        break
    _current = _current.parent

from python_utils.common_objects.debuggable import Debuggable
from python_utils.io_utils.json_io import write_json, PartsKeyPath


# --- Mock data (mirrors WebDriverActionResult) ---

def make_mock_action_result():
    return {
        'body_html_before_last_action': (
            '<html><body>\n'
            '  <h1>Product Page</h1>\n'
            '  <p>Price: $29.99</p>\n'
            '  <button id="add-to-cart">Add to Cart</button>\n'
            '</body></html>'
        ),
        'body_html_after_last_action': (
            '<html><body>\n'
            '  <h1>Product Page</h1>\n'
            '  <p>Price: $29.99</p>\n'
            '  <button id="add-to-cart" disabled>Added!</button>\n'
            '  <div class="cart-popup">Item added to cart (1 item)</div>\n'
            '</body></html>'
        ),
        'cleaned_body_html_after_last_action': (
            '<div>\n'
            '  <h1>Product Page</h1>\n'
            '  <p>Price: $29.99</p>\n'
            '  <button disabled>Added!</button>\n'
            '  <div class="cart-popup">Item added to cart</div>\n'
            '</div>'
        ),
        'is_cleaned_body_html_only_incremental_change': False,
        'source': 'playwright',
        'action_type': 'click',
        'target': '#add-to-cart',
    }


# --- Debuggable subclass (like WebDriver) ---

class MockWebDriver(Debuggable):
    """Simplified stand-in for WebDriver that logs action results."""

    def execute_action(self):
        result = make_mock_action_result()

        # This is the exact pattern from web_driver.py.
        # Note: Debuggable wraps `result` under an 'item' key in log_data,
        # so the key paths must be 'item.field_name'.
        self.log_info(
            result,
            'AgentActionResults',
            parts_key_paths=[
                PartsKeyPath('item.body_html_before_last_action', ext='.html',
                             alias='BeforeHtml', subfolder='ui_source'),
                PartsKeyPath('item.body_html_after_last_action', ext='.html',
                             alias='AfterHtml', subfolder='ui_source'),
                PartsKeyPath('item.cleaned_body_html_after_last_action', ext='.html',
                             alias='CleanedHtml', subfolder='ui_source'),
            ],
            parts_min_size=0,
        )
        return result


# --- Run ---

def main():
    # 1. Setup output directory and logger
    output_dir = Path(__file__).parent / '_output'
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir()

    log_file = str(output_dir / 'actions.jsonl')
    driver = MockWebDriver(
        debug_mode=True,
        logger=partial(write_json, file_path=log_file),
        always_add_logging_based_logger=False,
        log_time=False,
    )

    # 2. Execute action (triggers log_info → write_json → parts extraction)
    driver.execute_action()

    # 3. Collect results for display
    actual_file = os.path.join(log_file, driver.id)
    parts_dir = actual_file + '.parts'

    dir_tree_lines = []
    for root, dirs, files in os.walk(output_dir):
        level = str(root).replace(str(output_dir), '').count(os.sep)
        indent = '  ' * level
        dir_tree_lines.append(f'{indent}{os.path.basename(root)}/')
        for f in sorted(files):
            size = os.path.getsize(os.path.join(root, f))
            dir_tree_lines.append(f'{indent}  {f}  ({size} bytes)')

    with open(actual_file, 'r', encoding='utf-8') as f:
        main_json = json.loads(f.readline())

    sample_parts_file = os.path.join(parts_dir, 'ui_source', 'AfterHtml.html')
    with open(sample_parts_file, 'r', encoding='utf-8') as f:
        sample_html = f.read()

    # 4. Print everything
    sep = '=' * 60
    print(sep)
    print('Parts Extraction Example')
    print(sep)
    print(f'Output directory: {output_dir}\n')

    print('Directory structure:')
    print('\n'.join(dir_tree_lines))

    print(f'\n{sep}')
    print(f'Main JSON ({os.path.basename(actual_file)}):')
    print(sep)
    print(json.dumps(main_json, indent=2))

    print(f'\n{sep}')
    print('Extracted parts file (ui_source/AfterHtml.html):')
    print(sep)
    print(sample_html)

    print(f'\n{sep}')
    print(f'Examine the full output at:\n  {output_dir}')
    print(sep)


if __name__ == '__main__':
    main()
