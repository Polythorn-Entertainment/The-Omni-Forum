#!/usr/bin/env python3
"""Build deploy-friendly concatenated CSS and JS assets from the manifest."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
IMPORT_RE = re.compile(r"@import\s+url\([\"']?([^\"')]+)[\"']?\);?")


def load_manifest() -> dict[str, Any]:
    return json.loads((ROOT / "assets" / "manifest.json").read_text(encoding="utf-8"))


def resolve_css(path: Path, seen: set[Path] | None = None) -> str:
    seen = seen or set()
    path = path.resolve()
    if path in seen:
        return ""
    seen.add(path)
    text = path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        target = (path.parent / match.group(1)).resolve()
        return resolve_css(target, seen)

    return IMPORT_RE.sub(replace, text)


def concat_js(paths: list[str]) -> str:
    parts = []
    for asset in paths:
        path = ROOT / asset
        parts.append(f"/* {asset} */\n{path.read_text(encoding='utf-8').rstrip()}\n")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", help="directory to write concatenated assets into")
    args = parser.parse_args()

    manifest = load_manifest()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    css = "\n".join(resolve_css(ROOT / asset) for asset in manifest["styles"])
    (out / "omniforum.css").write_text(css, encoding="utf-8")
    shared = list(manifest["sharedScripts"])
    (out / "omniforum-shared.js").write_text(concat_js(shared), encoding="utf-8")
    for page, scripts in manifest["pages"].items():
        name = page.replace("/", "-").replace(".html", "")
        (out / f"{name}.js").write_text(concat_js(list(scripts)), encoding="utf-8")
    print(f"built deploy assets in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
