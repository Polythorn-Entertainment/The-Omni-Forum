#!/usr/bin/env python3
"""Lightweight frontend structure checks for split JS/CSS assets."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPORT_RE = re.compile(r"@import\s+url\([\"']?([^\"')]+)[\"']?\)")


def check_css_imports() -> list[str]:
    errors: list[str] = []
    for path in sorted((ROOT / "css").glob("*.css")):
        text = path.read_text(encoding="utf-8")
        if text.count("{") != text.count("}"):
            errors.append(f"{path.relative_to(ROOT)}: mismatched CSS braces")
        for target in IMPORT_RE.findall(text):
            resolved = (path.parent / target).resolve()
            if not resolved.is_file() or ROOT not in resolved.parents:
                errors.append(f"{path.relative_to(ROOT)}: missing CSS import {target}")
    return errors


def check_js_syntax() -> list[str]:
    errors: list[str] = []
    for path in sorted((ROOT / "js").glob("*.js")):
        result = subprocess.run(
            ["node", "--check", str(path)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode:
            errors.append(result.stdout.strip())
    return errors


def check_manifest_duplicates() -> list[str]:
    errors: list[str] = []
    manifest = json.loads((ROOT / "assets" / "manifest.json").read_text(encoding="utf-8"))
    shared = manifest.get("sharedScripts", [])
    if len(shared) != len(set(shared)):
        errors.append("assets/manifest.json: duplicate shared scripts")
    for page, scripts in manifest.get("pages", {}).items():
        combined = shared + scripts
        if len(combined) != len(set(combined)):
            errors.append(f"assets/manifest.json: duplicate scripts for {page}")
    return errors


def main() -> int:
    errors = check_css_imports() + check_js_syntax() + check_manifest_duplicates()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("frontend checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
