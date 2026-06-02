#!/usr/bin/env python3
"""Update HTML asset tags from the checked-in asset manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "assets" / "manifest.json"
STYLE_BLOCK_RE = re.compile(
    r"(?:<!-- ASSET STYLES -->\n)?(?:<link rel=\"stylesheet\" href=\"[^\"]+\">\n)+",
    re.MULTILINE,
)
SCRIPT_BLOCK_RE = re.compile(
    r"(?:<!-- ASSET SCRIPTS -->\n)?(?:<script src=\"[^\"]+\"></script>\n)+(?=</body>)",
    re.MULTILINE,
)


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def html_prefix(page_path: Path) -> str:
    return "" if page_path.parent == ROOT else "../"


def render_styles(styles: list[str], prefix: str) -> str:
    links = [f'<link rel="stylesheet" href="{prefix}{path}">' for path in styles]
    return "<!-- ASSET STYLES -->\n" + "\n".join(links) + "\n"


def render_scripts(scripts: list[str], prefix: str) -> str:
    tags = [f'<script src="{prefix}{path}"></script>' for path in scripts]
    return "<!-- ASSET SCRIPTS -->\n" + "\n".join(tags) + "\n"


def page_scripts(manifest: dict[str, Any], page: str) -> list[str]:
    return list(manifest["sharedScripts"]) + list(manifest["pages"][page])


def expected_html(path: Path, manifest: dict[str, Any]) -> str:
    page_key = path.relative_to(ROOT).as_posix()
    prefix = html_prefix(path)
    text = path.read_text(encoding="utf-8")
    text, style_count = STYLE_BLOCK_RE.subn(render_styles(manifest["styles"], prefix), text, count=1)
    text, script_count = SCRIPT_BLOCK_RE.subn(render_scripts(page_scripts(manifest, page_key), prefix), text, count=1)
    if style_count != 1:
        raise ValueError(f"{page_key}: expected exactly one stylesheet block")
    if script_count != 1:
        raise ValueError(f"{page_key}: expected exactly one script block before </body>")
    return text


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    seen_pages = set(manifest.get("pages", {}))
    actual_pages = {"index.html"} | {path.as_posix() for path in Path("pages").glob("*.html")}
    for page in sorted(actual_pages - seen_pages):
        errors.append(f"missing page in manifest: {page}")
    for page in sorted(seen_pages - actual_pages):
        errors.append(f"manifest page does not exist: {page}")
    assets = list(manifest.get("styles", [])) + list(manifest.get("sharedScripts", []))
    for scripts in manifest.get("pages", {}).values():
        assets.extend(scripts)
    for asset in sorted(set(assets)):
        if not (ROOT / asset).is_file():
            errors.append(f"manifest asset does not exist: {asset}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if HTML asset tags are not up to date")
    args = parser.parse_args()

    manifest = load_manifest()
    errors = validate_manifest(manifest)
    changed: list[str] = []
    for page in sorted(manifest["pages"]):
        path = ROOT / page
        try:
            expected = expected_html(path, manifest)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        current = path.read_text(encoding="utf-8")
        if expected != current:
            changed.append(page)
            if not args.check:
                path.write_text(expected, encoding="utf-8")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if args.check and changed:
        for page in changed:
            print(f"asset tags are stale: {page}", file=sys.stderr)
        return 1
    if changed:
        print("updated asset tags: " + ", ".join(changed))
    else:
        print("asset tags are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
