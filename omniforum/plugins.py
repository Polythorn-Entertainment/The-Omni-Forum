"""Plugin manifest and public asset helpers."""

from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
from typing import Any

from .config import PLUGIN_ASSET_EXTENSIONS, PLUGIN_DIR
from .errors import APIError
from .validation import clean_slug, clean_text


def get_plugin_status_summary(plugins: list[dict[str, Any]]) -> dict[str, Any]:
    enabled = sum(1 for plugin in plugins if plugin.get("enabled"))
    disabled = sum(1 for plugin in plugins if not plugin.get("enabled"))
    with_assets = sum(1 for plugin in plugins if plugin.get("hasClientAssets"))
    asset_counts = {
        "styles": sum(int(plugin.get("assetCounts", {}).get("styles") or 0) for plugin in plugins),
        "scripts": sum(int(plugin.get("assetCounts", {}).get("scripts") or 0) for plugin in plugins),
        "assets": sum(int(plugin.get("assetCounts", {}).get("assets") or 0) for plugin in plugins),
    }
    invalid_directories: list[str] = []
    if PLUGIN_DIR.exists():
        for plugin_root in sorted(path for path in PLUGIN_DIR.iterdir() if path.is_dir()):
            if not load_plugin_manifest(plugin_root):
                invalid_directories.append(plugin_root.name)
    return {
        "total": len(plugins),
        "enabled": enabled,
        "disabled": disabled,
        "withClientAssets": with_assets,
        "invalidCount": len(invalid_directories),
        "invalidDirectories": invalid_directories,
        "assetCounts": asset_counts,
        "status": "warning" if invalid_directories else "healthy",
    }


def resolve_plugin_asset(plugin_root: Path, relative_path: str) -> Path | None:
    relative = str(relative_path or "").strip().replace("\\", "/").strip("/")
    if not relative:
        return None
    candidate = (plugin_root / relative).resolve()
    if plugin_root.resolve() not in {candidate, *candidate.parents}:
        return None
    if not candidate.is_file():
        return None
    return candidate


def load_plugin_manifest(plugin_root: Path) -> tuple[Path, dict[str, Any]] | None:
    manifest_path = plugin_root / "plugin.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(manifest, dict):
        return None
    return manifest_path, manifest


def plugin_client_assets(
    plugin_root: Path,
    manifest: dict[str, Any],
) -> dict[str, list[dict[str, str]]]:
    client = manifest.get("client") or {}
    assets: dict[str, list[dict[str, str]]] = {
        "styles": [],
        "scripts": [],
        "assets": [],
    }
    for bucket in ("styles", "scripts", "assets"):
        for item in client.get(bucket, []):
            resolved = resolve_plugin_asset(plugin_root, str(item))
            if not resolved:
                continue
            extension = resolved.suffix.lower()
            if extension not in PLUGIN_ASSET_EXTENSIONS:
                continue
            relative = resolved.relative_to(plugin_root).as_posix()
            assets[bucket].append(
                {
                    "path": relative,
                    "url": f"/plugins/{plugin_root.name}/{relative}",
                }
            )
    return assets


def serialize_plugin(plugin_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    plugin_id = clean_slug(manifest.get("id") or plugin_root.name, fallback=plugin_root.name)
    enabled = bool(manifest.get("enabled", True))
    assets = plugin_client_assets(plugin_root, manifest)
    styles = [item["url"] for item in assets["styles"]]
    scripts = [item["url"] for item in assets["scripts"]]
    public_assets = [item["url"] for item in assets["assets"]]
    return {
        "id": plugin_id,
        "directory": plugin_root.name,
        "name": clean_text(manifest.get("name") or plugin_root.name, min_len=1, max_len=80, field="Plugin name"),
        "version": clean_text(manifest.get("version") or "0.0.0", min_len=1, max_len=32, field="Plugin version"),
        "description": clean_text(manifest.get("description"), min_len=0, max_len=200, field="Plugin description"),
        "enabled": enabled,
        "author": clean_text(manifest.get("author"), min_len=0, max_len=80, field="Plugin author"),
        "styles": styles,
        "scripts": scripts,
        "assets": public_assets,
        "assetCounts": {
            "styles": len(styles),
            "scripts": len(scripts),
            "assets": len(public_assets),
        },
        "hasClientAssets": bool(styles or scripts or public_assets),
        "safeLoadingRules": {
            "enabledOnly": True,
            "manifestDeclaredOnly": True,
            "allowedExtensions": sorted(PLUGIN_ASSET_EXTENSIONS),
        },
    }


def list_plugins(*, include_disabled: bool = True) -> list[dict[str, Any]]:
    if not PLUGIN_DIR.exists():
        return []
    output: list[dict[str, Any]] = []
    for plugin_root in sorted(path for path in PLUGIN_DIR.iterdir() if path.is_dir()):
        loaded = load_plugin_manifest(plugin_root)
        if not loaded:
            continue
        _manifest_path, manifest = loaded
        enabled = bool(manifest.get("enabled", True))
        if not include_disabled and not enabled:
            continue
        output.append(serialize_plugin(plugin_root, manifest))
    return output


def get_plugin_record(plugin_id: str) -> tuple[Path, Path, dict[str, Any]] | None:
    requested = clean_slug(plugin_id or "", fallback="")
    if not requested or not PLUGIN_DIR.exists():
        return None
    for plugin_root in sorted(path for path in PLUGIN_DIR.iterdir() if path.is_dir()):
        loaded = load_plugin_manifest(plugin_root)
        if not loaded:
            continue
        manifest_path, manifest = loaded
        current_id = clean_slug(manifest.get("id") or plugin_root.name, fallback=plugin_root.name)
        if current_id == requested or plugin_root.name == requested:
            return plugin_root, manifest_path, manifest
    return None


def set_plugin_enabled(plugin_id: str, enabled: bool) -> dict[str, Any]:
    record = get_plugin_record(plugin_id)
    if not record:
        raise APIError("Plugin not found.", HTTPStatus.NOT_FOUND)
    plugin_root, manifest_path, manifest = record
    manifest["enabled"] = bool(enabled)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return serialize_plugin(plugin_root, manifest)


def resolve_public_plugin_asset(directory: str, relative_path: str) -> tuple[Path, Path, dict[str, Any], Path] | None:
    plugin_root = (PLUGIN_DIR / directory).resolve()
    if PLUGIN_DIR.resolve() not in {plugin_root, *plugin_root.parents} or not plugin_root.is_dir():
        return None
    loaded = load_plugin_manifest(plugin_root)
    if not loaded:
        return None
    manifest_path, manifest = loaded
    if not bool(manifest.get("enabled", True)):
        return None
    allowed_paths = {
        item["path"]
        for bucket in plugin_client_assets(plugin_root, manifest).values()
        for item in bucket
    }
    normalized = str(relative_path or "").strip().replace("\\", "/").strip("/")
    if normalized not in allowed_paths:
        return None
    resolved = resolve_plugin_asset(plugin_root, normalized)
    if not resolved or resolved.suffix.lower() not in PLUGIN_ASSET_EXTENSIONS:
        return None
    return plugin_root, manifest_path, manifest, resolved
