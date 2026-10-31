# Task 1 Report: Version Resolution & File Metadata Formatting

## Status
DONE

## Commit Hash
`4708cd1b91203023a2f95e1f2bd75be5a875b2a9`

## Test Results
- Pytest command: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe`
- Total tests executed: 20 passed (8 in `tests/test_file_select.py`, 4 in `tests/test_focus.py`, 4 in `tests/test_progress.py`, 4 in `tests/test_session.py`).
- 0 failures, 0 errors.

## Implementation Details
1. **Dynamic Version Loading (`src/riptide/__init__.py`)**:
   - Implemented `_load_version()` using `tomllib` to dynamically read version from `pyproject.toml`, with graceful fallback to `importlib.metadata.version("riptide")` and default `"0.0.0"`.
2. **Metadata Formatting (`src/riptide/core/file_select.py`)**:
   - Implemented `format_mtime(mtime: float) -> str` enforcing strict `dd-mm-yyyy hh:mm am/pm` lowercase timestamp formatting.
   - Implemented `format_file_row(path: Path) -> tuple[str, str, str]` returning `(path.name, format_bytes(stat.st_size), format_mtime(stat.st_mtime))`.
3. **Tests (`tests/test_file_select.py`)**:
   - Added `test_dynamic_version_matches_pyproject`.
   - Added `test_format_mtime_exact_format`.
   - Added `test_format_file_row`.
