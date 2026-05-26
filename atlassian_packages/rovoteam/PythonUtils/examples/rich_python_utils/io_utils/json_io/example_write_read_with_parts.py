"""
Example: Writing and reading JSON with parts extraction.

Scenario — You're collecting research articles from the web.  Each article has
compact metadata (title, author, date) plus bulky content (raw HTML, cleaned
text).  Storing everything in a single JSON file makes the file huge and hard
to browse.  Parts extraction solves this: the bulky fields are automatically
saved as separate files under a ``.parts/`` directory, while the main JSON
keeps a lightweight reference.  When you read the JSON back with
``resolve_parts=True``, the original data is seamlessly reassembled.

What this example demonstrates:
  1. write_json with parts_key_paths   — extract specific fields into .parts/
  2. iter_json_objs with resolve_parts — read them back, fully reassembled
  3. resolve_json_parts                — standalone resolution on any dict
  4. leaf_as_parts_if_exceeding_size   — auto-extract any oversized string
  5. Different replacement modes       — reference vs truncate

Prerequisites:
    No external dependencies (uses standard library)

Usage:
    python example_write_read_with_parts.py
"""

import json
import os
import shutil
from pathlib import Path

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.io_utils.json_io import (
    write_json,
    iter_json_objs,
    resolve_json_parts,
    PartsKeyPath,
)


# ---------------------------------------------------------------------------
# Sample data — three research articles scraped from the web
# ---------------------------------------------------------------------------

ARTICLES = [
    {
        'id': 'article-001',
        'title': 'The Rise of Renewable Energy in Southeast Asia',
        'author': 'Dr. Lin Wei',
        'published': '2025-09-15',
        'tags': ['energy', 'sustainability', 'policy'],
        'body_html': (
            '<!DOCTYPE html><html><head><title>Renewable Energy</title></head>'
            '<body>'
            '<h1>The Rise of Renewable Energy in Southeast Asia</h1>'
            '<p>Southeast Asia is undergoing a dramatic transformation in its '
            'energy landscape.  Countries like Vietnam, Thailand, and the '
            'Philippines have accelerated their solar and wind capacity, '
            'driven by falling costs and ambitious government targets.</p>'
            '<p>Vietnam alone added 16 GW of solar capacity between 2019 and '
            '2023, making it the region\'s leader.  Meanwhile, offshore wind '
            'projects in Taiwan and the Philippines are attracting billions '
            'in foreign investment.</p>'
            '<h2>Key Challenges</h2>'
            '<p>Grid integration remains the biggest hurdle.  Intermittent '
            'supply from solar and wind requires substantial investment in '
            'battery storage and cross-border interconnectors.</p>'
            '</body></html>'
        ),
        'cleaned_text': (
            'The Rise of Renewable Energy in Southeast Asia\n\n'
            'Southeast Asia is undergoing a dramatic transformation in its '
            'energy landscape.  Countries like Vietnam, Thailand, and the '
            'Philippines have accelerated their solar and wind capacity, '
            'driven by falling costs and ambitious government targets.\n\n'
            'Vietnam alone added 16 GW of solar capacity between 2019 and '
            '2023, making it the region\'s leader.  Meanwhile, offshore wind '
            'projects in Taiwan and the Philippines are attracting billions '
            'in foreign investment.\n\n'
            'Key Challenges\n\n'
            'Grid integration remains the biggest hurdle.  Intermittent '
            'supply from solar and wind requires substantial investment in '
            'battery storage and cross-border interconnectors.'
        ),
    },
    {
        'id': 'article-002',
        'title': 'How Large Language Models Are Reshaping Scientific Discovery',
        'author': 'Prof. Sarah Chen',
        'published': '2025-10-02',
        'tags': ['AI', 'science', 'LLM'],
        'body_html': (
            '<!DOCTYPE html><html><head><title>LLMs in Science</title></head>'
            '<body>'
            '<h1>How Large Language Models Are Reshaping Scientific Discovery</h1>'
            '<p>From protein folding to materials science, large language '
            'models are proving to be powerful assistants in the research '
            'pipeline.  They can summarise thousands of papers, suggest '
            'hypotheses, and even write preliminary code for simulations.</p>'
            '<p>However, hallucination remains a serious concern.  A model '
            'that confidently cites a non-existent study can derail an '
            'entire research programme if its outputs are not carefully '
            'verified.</p>'
            '<h2>Best Practices</h2>'
            '<ul>'
            '<li>Always cross-reference model outputs with primary sources</li>'
            '<li>Use retrieval-augmented generation to ground responses</li>'
            '<li>Keep a human in the loop for critical decisions</li>'
            '</ul>'
            '</body></html>'
        ),
        'cleaned_text': (
            'How Large Language Models Are Reshaping Scientific Discovery\n\n'
            'From protein folding to materials science, large language '
            'models are proving to be powerful assistants in the research '
            'pipeline.  They can summarise thousands of papers, suggest '
            'hypotheses, and even write preliminary code for simulations.\n\n'
            'However, hallucination remains a serious concern.  A model '
            'that confidently cites a non-existent study can derail an '
            'entire research programme if its outputs are not carefully '
            'verified.\n\n'
            'Best Practices\n\n'
            '- Always cross-reference model outputs with primary sources\n'
            '- Use retrieval-augmented generation to ground responses\n'
            '- Keep a human in the loop for critical decisions'
        ),
    },
    {
        'id': 'article-003',
        'title': 'Urban Farming: Feeding Cities from Rooftops and Basements',
        'author': 'Maria Gonzalez',
        'published': '2025-11-20',
        'tags': ['agriculture', 'urban', 'food-security'],
        'body_html': (
            '<!DOCTYPE html><html><head><title>Urban Farming</title></head>'
            '<body>'
            '<h1>Urban Farming: Feeding Cities from Rooftops and Basements</h1>'
            '<p>Vertical farms and rooftop gardens are sprouting up in major '
            'cities worldwide.  Singapore, Tokyo, and New York have become '
            'hotbeds for startups that grow leafy greens, herbs, and even '
            'strawberries in controlled indoor environments.</p>'
            '<p>The economics are improving rapidly.  LED lighting costs have '
            'dropped 90% since 2010, and AI-driven climate control can '
            'optimise yields while cutting water usage by up to 95% compared '
            'to traditional field farming.</p>'
            '</body></html>'
        ),
        'cleaned_text': (
            'Urban Farming: Feeding Cities from Rooftops and Basements\n\n'
            'Vertical farms and rooftop gardens are sprouting up in major '
            'cities worldwide.  Singapore, Tokyo, and New York have become '
            'hotbeds for startups that grow leafy greens, herbs, and even '
            'strawberries in controlled indoor environments.\n\n'
            'The economics are improving rapidly.  LED lighting costs have '
            'dropped 90% since 2010, and AI-driven climate control can '
            'optimise yields while cutting water usage by up to 95% compared '
            'to traditional field farming.'
        ),
    },
]


# ---------------------------------------------------------------------------
# Output directory (local, alongside this script)
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).resolve().parent / '_output'


def clean_output():
    """Remove the output directory to start fresh."""
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def print_tree(directory: Path, prefix: str = ''):
    """Print a directory tree in a human-friendly format."""
    entries = sorted(directory.iterdir(), key=lambda e: (e.is_file(), e.name))
    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = '`-- ' if is_last else '|-- '
        print(f'{prefix}{connector}{entry.name}')
        if entry.is_dir():
            extension = '    ' if is_last else '|   '
            print_tree(entry, prefix + extension)


# ===== Example 1 =============================================================

def example_basic_parts_extraction():
    """Write articles as JSONL, extracting body_html and cleaned_text into
    separate .parts/ files so the main JSON stays compact.
    """
    print('\n' + '=' * 80)
    print('EXAMPLE 1: Basic Parts Extraction (write) + Resolution (read)')
    print('=' * 80)

    log_file = str(OUTPUT_DIR / 'articles.json')

    # ---- Core logic: write articles with parts extraction ----
    for i, article in enumerate(ARTICLES):
        write_json(
            article,
            log_file,
            append=(i > 0),              # first write creates, rest append
            parts_key_paths=[
                PartsKeyPath('body_html', ext='.html'),
                PartsKeyPath('cleaned_text', ext='.txt'),
            ],
            parts_min_size=0,            # extract regardless of size
        )

    # Read back with references still in place (resolve_parts=False)
    unresolved = list(iter_json_objs(log_file, resolve_parts=False))

    # Read back with full reassembly (resolve_parts=True)
    resolved = list(iter_json_objs(log_file, resolve_parts=True))

    # ---- Display results ----
    print('\n--- Writing 3 articles with parts extraction ---')
    for a in ARTICLES:
        print(f'  Wrote: {a["id"]} - {a["title"][:50]}...')

    print('\n--- File structure on disk ---')
    print_tree(OUTPUT_DIR)

    print('\n--- Main JSON content (compact -- references only) ---')
    for obj in unresolved:
        print(f'  {obj["id"]}: body_html -> {obj["body_html"]}')

    print('\n--- Reading back with resolve_parts=True ---')
    for article in resolved:
        print(f'  {article["id"]}: {article["title"]}')
        print(f'    body_html   : {article["body_html"][:80]}...')
        print(f'    cleaned_text: {article["cleaned_text"][:80]}...')
        print(f'    tags        : {article["tags"]}')
        print()

    print('  [OK] All articles fully reassembled from parts!')


# ===== Example 2 =============================================================

def example_standalone_resolve():
    """Use resolve_json_parts() to resolve a dict you loaded yourself,
    without going through iter_json_objs.
    """
    print('\n' + '=' * 80)
    print('EXAMPLE 2: Standalone resolve_json_parts()')
    print('=' * 80)

    log_file = str(OUTPUT_DIR / 'single_article.json')

    # ---- Core logic: write, load with plain json, then resolve ----
    write_json(
        ARTICLES[0],
        log_file,
        parts_key_paths=[PartsKeyPath('body_html', ext='.html')],
        parts_min_size=0,
    )

    with open(log_file, 'r', encoding='utf-8') as f:
        raw = json.loads(f.readline())

    resolved = resolve_json_parts(raw, log_file)

    # ---- Display results ----
    print('\n--- Loading with json.load (references unresolved) ---')
    print(f'  body_html type : {type(raw["body_html"]).__name__}')
    print(f'  body_html value: {raw["body_html"]}')

    print('\n--- After resolve_json_parts() ---')
    print(f'  body_html type : {type(resolved["body_html"]).__name__}')
    print(f'  body_html value: {resolved["body_html"][:80]}...')

    print('\n  [OK] Resolved without iter_json_objs!')


# ===== Example 3 =============================================================

def example_auto_extract_oversized():
    """Use leaf_as_parts_if_exceeding_size to automatically extract any
    string field that exceeds a size threshold -- no need to list keys.
    """
    print('\n' + '=' * 80)
    print('EXAMPLE 3: Auto-Extract Oversized Fields')
    print('=' * 80)

    log_file = str(OUTPUT_DIR / 'auto_extract.json')

    # ---- Core logic: write with auto-extraction, then read back ----
    write_json(
        ARTICLES[1],
        log_file,
        leaf_as_parts_if_exceeding_size=200,
    )

    unresolved = list(iter_json_objs(log_file, resolve_parts=False))
    resolved = list(iter_json_objs(log_file, resolve_parts=True))

    # ---- Display results ----
    print('\n--- Writing with leaf_as_parts_if_exceeding_size=200 ---')
    print('\n--- Main JSON (fields under 200 chars stay inline) ---')
    for obj in unresolved:
        for key, val in obj.items():
            if isinstance(val, dict) and '__parts_file__' in val:
                print(f'  {key:15s} -> [extracted to {val["__parts_file__"]}]')
            else:
                display = str(val)
                if len(display) > 60:
                    display = display[:60] + '...'
                print(f'  {key:15s} -> {display}')

    print('\n--- Read back with resolve_parts=True ---')
    for obj in resolved:
        print(f'  title       : {obj["title"]}')
        print(f'  body_html   : {obj["body_html"][:80]}...')
        print(f'  cleaned_text: {obj["cleaned_text"][:80]}...')

    print('\n  [OK] Oversized fields auto-extracted and reassembled!')


# ===== Example 4 =============================================================

def example_truncate_mode():
    """Use parts_mode='truncate' to keep a readable preview in the main
    JSON instead of a reference dict.  Useful for quick browsing.
    """
    print('\n' + '=' * 80)
    print('EXAMPLE 4: Truncate Mode (human-readable preview in main JSON)')
    print('=' * 80)

    log_file = str(OUTPUT_DIR / 'truncated.json')

    # ---- Core logic: write with truncate mode ----
    write_json(
        ARTICLES[2],
        log_file,
        parts_key_paths=[
            PartsKeyPath('body_html', ext='.html'),
            PartsKeyPath('cleaned_text', ext='.txt'),
        ],
        parts_min_size=0,
        parts_mode='truncate',
        parts_preview_len=100,
    )

    with open(log_file, 'r', encoding='utf-8') as f:
        obj = json.loads(f.readline())

    # ---- Display results ----
    print('\n--- Writing with parts_mode="truncate" ---')
    print('\n--- Main JSON (truncated previews) ---')
    print(f'  title       : {obj["title"]}')
    print(f'  body_html   : {obj["body_html"][:120]}...')
    print(f'  cleaned_text: {obj["cleaned_text"][:120]}...')

    print('\n  Note: Truncate mode is for human browsing -- the full content')
    print('  is still saved in the .parts/ directory, but the main JSON')
    print('  shows a preview instead of a machine-readable reference.')
    print('  Use "reference" mode (the default) for round-trip fidelity.')


# ===== Example 5 =============================================================

def example_subfolder_organisation():
    """Use PartsKeyPath(subfolder=...) and parts_subfolder to organise
    extracted files into meaningful subdirectories.
    """
    print('\n' + '=' * 80)
    print('EXAMPLE 5: Organising Parts with Subfolders')
    print('=' * 80)

    log_file = str(OUTPUT_DIR / 'organised.json')

    # ---- Core logic: write with per-field subfolders, then read back ----
    for i, article in enumerate(ARTICLES):
        write_json(
            article,
            log_file,
            append=(i > 0),
            parts_key_paths=[
                PartsKeyPath('body_html', ext='.html', subfolder='raw_html'),
                PartsKeyPath('cleaned_text', ext='.txt', subfolder='clean_text'),
            ],
            parts_min_size=0,
        )

    resolved = list(iter_json_objs(log_file, resolve_parts=True))

    # ---- Display results ----
    print('\n--- Writing with per-field subfolders ---')
    print('\n--- File structure (parts neatly grouped) ---')
    print_tree(OUTPUT_DIR / 'organised.json.parts')

    print('\n--- Round-trip verification ---')
    for article in resolved:
        print(f'  {article["id"]}: body_html={len(article["body_html"])} chars, '
              f'cleaned_text={len(article["cleaned_text"])} chars')

    print('\n  [OK] Subfolders keep .html and .txt files neatly separated!')


# ===== Example 6 =============================================================

def example_read_from_directory():
    """Write articles into separate JSON files under a directory, each
    with its own .parts/ folder.  Then read them all back at once.
    """
    print('\n' + '=' * 80)
    print('EXAMPLE 6: Reading from a Directory of JSON Files')
    print('=' * 80)

    articles_dir = OUTPUT_DIR / 'articles_dir'
    articles_dir.mkdir(parents=True, exist_ok=True)

    # ---- Core logic: one file per article, then read entire directory ----
    for article in ARTICLES:
        write_json(
            article,
            str(articles_dir / f'{article["id"]}.json'),
            parts_key_paths=[
                PartsKeyPath('body_html', ext='.html'),
                PartsKeyPath('cleaned_text', ext='.txt'),
            ],
            parts_min_size=0,
        )

    resolved = list(iter_json_objs(str(articles_dir), resolve_parts=True))

    # ---- Display results ----
    print('\n--- Writing each article to its own file ---')
    for a in ARTICLES:
        print(f'  Created: {a["id"]}.json + {a["id"]}.json.parts/')

    print('\n--- File structure ---')
    print_tree(articles_dir)

    print('\n--- iter_json_objs(directory, resolve_parts=True) ---')
    for article in resolved:
        print(f'  {article["id"]}: {article["title"]}')
        print(f'    author   : {article["author"]}, tags: {article["tags"]}')
        print(f'    body_html: {article["body_html"][:60]}...')
        print()

    print('  [OK] All files in the directory read and reassembled!')


# ===========================================================================

def main():
    print("""
==============================================================================
          JSON Write/Read with Parts Extraction -- Examples
==============================================================================

Scenario: You're collecting research articles from the web.  Each article has
compact metadata (title, author, date) plus bulky content (raw HTML, cleaned
text).  Parts extraction keeps your main JSON files small and browsable, while
the full content lives in neatly organised .parts/ folders.
""")

    clean_output()

    examples = [
        example_basic_parts_extraction,
        example_standalone_resolve,
        example_auto_extract_oversized,
        example_truncate_mode,
        example_subfolder_organisation,
        example_read_from_directory,
    ]

    for example_func in examples:
        try:
            example_func()
        except Exception as e:
            print(f'\n  [FAILED] {e}')
            import traceback
            traceback.print_exc()

    print('\n' + '=' * 80)
    print('[OK] All examples completed!')
    print(f'Output files are in: {OUTPUT_DIR}')
    print('=' * 80 + '\n')


if __name__ == '__main__':
    main()
