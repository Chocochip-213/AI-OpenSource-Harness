#!/usr/bin/env python3
"""Smoke test: basic import checks + compileall on the project."""

import os
import py_compile
import subprocess
import sys
from pathlib import Path


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def compile_all_python(repo: Path) -> list[str]:
    """Run py_compile on every .py file, return list of failures."""
    failures = []
    for py_file in repo.rglob("*.py"):
        # Skip hidden dirs and __pycache__
        parts = py_file.relative_to(repo).parts
        if any(p.startswith(".") or p == "__pycache__" for p in parts):
            continue
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as e:
            failures.append(f"  {py_file.relative_to(repo)}: {e}")
    return failures


def check_critical_imports() -> list[str]:
    """Try importing stdlib modules used in this project."""
    failures = []
    for mod in ("json", "pathlib", "subprocess", "os", "sys", "yaml"):
        try:
            __import__(mod)
        except ImportError:
            failures.append(f"  Cannot import: {mod}")
    return failures


def main():
    repo = get_repo_root()
    print("[smoke_test] Starting...")

    all_failures = []

    # 1. compileall
    print("[smoke_test] Compiling all .py files...")
    compile_fails = compile_all_python(repo)
    if compile_fails:
        all_failures.extend(compile_fails)
        print(f"  FAIL: {len(compile_fails)} file(s) failed to compile")
    else:
        print("  OK: All .py files compile")

    # 2. critical imports
    print("[smoke_test] Checking critical imports...")
    import_fails = check_critical_imports()
    if import_fails:
        all_failures.extend(import_fails)
        print(f"  WARN: {len(import_fails)} import(s) unavailable (yaml may need pip install)")
    else:
        print("  OK: All critical imports available")

    # 3. Summary
    if all_failures:
        print(f"\n[smoke_test] {len(all_failures)} issue(s) found:")
        for f in all_failures:
            print(f)
        # Only fail on compile errors, not missing optional imports
        if compile_fails:
            sys.exit(1)
    else:
        print("\n[smoke_test] All checks passed.")


if __name__ == "__main__":
    main()
