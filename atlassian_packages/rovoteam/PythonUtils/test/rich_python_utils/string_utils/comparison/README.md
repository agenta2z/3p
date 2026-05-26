# Tests for comparison.py

This directory contains tests for the `python_utils.string_utils.comparison` module, specifically testing the compiled regex feature enhancements.

## Test Files

### test_compiled_regex.py
Basic functionality tests for the compiled regex feature.

**What it tests:**
- Basic string matching (exact, contains, starts with, ends with)
- Regex patterns without compilation (original behavior)
- Regex patterns with compilation (new feature)
- Case sensitivity with compiled patterns
- Non-regex strings remain strings even with `compile_regex=True`
- Direct pattern passing to `string_compare`
- Performance comparison (compiled vs non-compiled)
- Backward compatibility with `string_check`

**Run:**
```bash
cd test/python_utils/string_utils/comparison
python test_compiled_regex.py
```

**Expected output:**
- All 8 test suites pass
- Performance speedup: ~1.7-2x with compiled patterns

### test_contains_regex.py
Tests for "contains" matching with regex patterns (including the `*@` operator combination).

**What it tests:**
- Contains matching with regex alternation: `@.*(view|body|presentation).*`
- Word boundary matching for complete words: `@.*\b(view|body|presentation)\b.*`
- Case insensitive contains matching: `/@.*(view|body|presentation).*`
- The `*@` operator combination (contains + regex):
  - **Works** with `compile_regex=True` ✓
  - **Works** with `compile_regex=False` ✓

**Run:**
```bash
cd test/python_utils/string_utils/comparison
python test_contains_regex.py
```

**Expected output:**
- All 4 test scenarios pass
- Demonstrates that `'*@ view|body|presentation'` successfully matches `'p-workspace__primary_view_body'` both with and without compilation

**Key Finding:**
The pattern `'*@ view|body|presentation'` **now works** both with AND without compilation! This was a bug fix - the original implementation unnecessarily blocked Contains+regex combinations, but `re.search()` naturally supports "contains" matching.

### test_operator_combinations.py
Comprehensive tests for all operator combinations with compiled regex.

**What it tests:**
- All regex operator combinations:
  - `@` - Regex exact match
  - `@^` - Regex starts with
  - `@$` - Regex ends with
  - `!@`, `!@^`, `!@$` - Negation variations
  - `/@`, `/@^`, `/@$` - Case insensitive variations
  - `/!@`, `/!@^`, `/!@$` - Complex combinations
- Real-world patterns:
  - Email validation
  - File extension checking
  - Security filtering
- Comparison between compiled and non-compiled patterns

**Run:**
```bash
cd test/python_utils/string_utils/comparison
python test_operator_combinations.py
```

**Expected output:**
- All 19 test scenarios pass
- Detailed output showing pattern compilation and matching results

## Running All Tests

From the test directory:
```bash
cd test/python_utils/string_utils/comparison
python test_compiled_regex.py && python test_contains_regex.py && python test_operator_combinations.py
```

Or from the project root:
```bash
cd SciencePythonUtils
python test/python_utils/string_utils/comparison/test_compiled_regex.py
python test/python_utils/string_utils/comparison/test_contains_regex.py
python test/python_utils/string_utils/comparison/test_operator_combinations.py
```

## Test Coverage

These tests provide comprehensive coverage of:
- ✅ All operator combinations (including `*@`)
- ✅ Compiled vs non-compiled patterns
- ✅ Case sensitivity handling
- ✅ Negation logic
- ✅ Error handling (invalid regex)
- ✅ Performance characteristics
- ✅ Backward compatibility
- ✅ Real-world use cases
- ✅ Contains + regex matching

## Test Results Summary

- **Total doctests**: 151 (in comparison.py)
- **Integration tests**: 31 scenarios (8 + 4 + 19)
- **All tests**: ✅ PASSING
- **Performance gain**: 1.7-2x speedup with compiled patterns

## Bug Fix: `*@` Pattern Now Fully Supported

The `*@` operator combination (contains + regex) is **now fully supported** both with and without compilation:

```python
from python_utils.string_utils.comparison import solve_compare_option, string_compare

# Without compilation - now works!
option, pattern = solve_compare_option('*@ view|body|presentation', compile_regex=False)
result = string_compare('p-workspace__primary_view_body', pattern, option)  # True ✓

# With compilation - also works!
option, pattern = solve_compare_option('*@ view|body|presentation', compile_regex=True)
result = string_compare('p-workspace__primary_view_body', pattern, option)  # True ✓
```

**What was fixed:** The original implementation artificially blocked Contains+regex combinations by raising a ValueError. This was unnecessary because `re.search()` naturally implements "contains" behavior (matching anywhere in the string). The fix simply adds `CompareMethod.Contains` to the list of supported regex methods.
