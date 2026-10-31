# Task 1 Brief: Version Resolution & File Metadata Formatting

## Objective
Implement dynamic project version loading from `pyproject.toml` in `src/riptide/__init__.py` and metadata formatting helpers in `src/riptide/core/file_select.py` (`format_mtime` with exact format `dd-mm-yyyy hh:mm am/pm` and `format_file_row`).

## Global Constraints
- Version must be dynamically loaded from `pyproject.toml` (variable `__version__`).
- Date format must strictly be `dd-mm-yyyy hh:mm am/pm` in lowercase (e.g. `31-10-2026 02:15 pm`).
- Python interpreter to use for pytest is `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe`.
- All 17 existing tests must continue to pass.

## Steps
1. Write failing tests in `tests/test_file_select.py` for:
   - `test_dynamic_version_matches_pyproject`
   - `test_format_mtime_exact_format`
   - `test_format_file_row`
2. Run tests to verify failure: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe tests/test_file_select.py -k "test_format_mtime"`
3. Implement `_load_version()` in `src/riptide/__init__.py` (reading `pyproject.toml` via `tomllib`).
4. Implement `format_mtime(mtime: float) -> str` and `format_file_row(path: Path) -> tuple[str, str, str]` in `src/riptide/core/file_select.py`.
5. Run tests to verify pass: `C:/Users/MpSingh/.venv-tools/Scripts/pytest.exe tests/test_file_select.py`
6. Commit: `git add src/riptide/__init__.py src/riptide/core/file_select.py tests/test_file_select.py && git commit -m "feat: add dynamic versioning and dd-mm-yyyy hh:mm am/pm file metadata formatting"`
7. Write summary to report file `.superpowers/sdd/task-1-report.md`.
