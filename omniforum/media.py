"""Media helper facade.

Path, quota, image-processing, storage, and post-media persistence helpers live in
focused media_* modules. This module keeps existing imports stable.
"""

from __future__ import annotations

from .media_images import (
    PIL_AVAILABLE,
    decode_image_upload,
    detect_image_type,
    encode_animated_image,
    encode_static_image,
    image_dimensions_from_bytes,
    image_has_alpha,
    jpeg_dimensions,
    normalize_media_uploads,
    pil_adaptive_palette,
    pil_resample_filter,
    process_image_upload_bytes,
    save_pillow_image,
    validate_image_geometry,
    webp_dimensions,
)
from .media_paths import delete_media_file, media_file_size, media_url_for_path, resolve_media_path
from .media_posts import (
    cleanup_orphan_post_artifacts,
    collect_post_media_paths,
    delete_post_artifact_rows,
    delete_post_media_files,
    list_post_media,
    list_post_media_rows,
    save_post_media_entries,
    serialize_post_media_row,
)
from .media_quota import ensure_user_media_quota, get_user_media_usage
from .media_store import store_image_upload, store_image_upload_paths

__all__ = [
    "PIL_AVAILABLE",
    "cleanup_orphan_post_artifacts",
    "collect_post_media_paths",
    "decode_image_upload",
    "delete_media_file",
    "delete_post_artifact_rows",
    "delete_post_media_files",
    "detect_image_type",
    "encode_animated_image",
    "encode_static_image",
    "ensure_user_media_quota",
    "get_user_media_usage",
    "image_dimensions_from_bytes",
    "image_has_alpha",
    "jpeg_dimensions",
    "list_post_media",
    "list_post_media_rows",
    "media_file_size",
    "media_url_for_path",
    "normalize_media_uploads",
    "pil_adaptive_palette",
    "pil_resample_filter",
    "process_image_upload_bytes",
    "resolve_media_path",
    "save_pillow_image",
    "save_post_media_entries",
    "serialize_post_media_row",
    "store_image_upload",
    "store_image_upload_paths",
    "validate_image_geometry",
    "webp_dimensions",
]
