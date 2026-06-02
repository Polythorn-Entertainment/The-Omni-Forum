"""Image upload decoding, validation, and processing helpers."""

from __future__ import annotations

import base64
import binascii
from io import BytesIO
from pathlib import Path
from typing import Any

from .config import (
    AVATAR_IMAGE_MAX_DIMENSION,
    JPEG_QUALITY,
    MAX_IMAGE_HEIGHT,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_WIDTH,
    POST_IMAGE_MAX_DIMENSION,
    POST_MEDIA_MAX_BYTES,
    POST_THUMBNAIL_MAX_DIMENSION,
    WEBP_QUALITY,
)
from .errors import APIError
from .validation import clean_text, slugify_text

try:
    from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

    PIL_AVAILABLE = True
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
except Exception:  # pragma: no cover - dependency availability is environment-specific.
    Image = ImageOps = ImageSequence = None
    UnidentifiedImageError = Exception
    PIL_AVAILABLE = False


def detect_image_type(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif", "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    raise APIError("Only PNG, JPG, GIF, and WEBP images are supported.")


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    index = 2
    while index < len(data):
        while index < len(data) and data[index] != 0xFF:
            index += 1
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        segment_length = int.from_bytes(data[index : index + 2], "big")
        if segment_length < 2 or index + segment_length > len(data):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if index + 7 > len(data):
                break
            height = int.from_bytes(data[index + 3 : index + 5], "big")
            width = int.from_bytes(data[index + 5 : index + 7], "big")
            return width, height
        index += segment_length
    raise APIError("Could not read that JPEG image.")


def webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30:
        raise APIError("Could not read that WEBP image.")
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if chunk == b"VP8L" and len(data) >= 25:
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    if chunk == b"VP8 " and len(data) >= 30:
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    raise APIError("Could not read that WEBP image.")


def image_dimensions_from_bytes(data: bytes, mime_type: str) -> tuple[int, int]:
    if mime_type == "image/png":
        if len(data) < 24:
            raise APIError("Could not read that PNG image.")
        return (
            int.from_bytes(data[16:20], "big"),
            int.from_bytes(data[20:24], "big"),
        )
    if mime_type == "image/gif":
        if len(data) < 10:
            raise APIError("Could not read that GIF image.")
        return (
            int.from_bytes(data[6:8], "little"),
            int.from_bytes(data[8:10], "little"),
        )
    if mime_type == "image/jpeg":
        return jpeg_dimensions(data)
    if mime_type == "image/webp":
        return webp_dimensions(data)
    raise APIError("Unsupported image type.")


def validate_image_geometry(data: bytes, mime_type: str, *, field: str) -> tuple[int, int]:
    width, height = image_dimensions_from_bytes(data, mime_type)
    if width < 1 or height < 1:
        raise APIError(f"{field} dimensions are invalid.")
    if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
        raise APIError(
            f"{field} is too large. Keep images under {MAX_IMAGE_WIDTH}px by {MAX_IMAGE_HEIGHT}px.",
        )
    if width * height > MAX_IMAGE_PIXELS:
        raise APIError(f"{field} has too many pixels for safe inline display.")
    return width, height


def pil_resample_filter():
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def pil_adaptive_palette():
    palette = getattr(Image, "Palette", None)
    return getattr(palette, "ADAPTIVE", getattr(Image, "ADAPTIVE", 1))


def image_has_alpha(image: Any) -> bool:
    if image.mode in {"RGBA", "LA"}:
        return True
    if image.mode == "P" and "transparency" in image.info:
        return True
    return False


def save_pillow_image(image: Any, image_format: str, **kwargs: Any) -> bytes:
    buffer = BytesIO()
    try:
        image.save(buffer, format=image_format, **kwargs)
    except OSError:
        kwargs.pop("optimize", None)
        buffer = BytesIO()
        image.save(buffer, format=image_format, **kwargs)
    return buffer.getvalue()


def encode_static_image(
    image: Any,
    *,
    source_mime_type: str,
    max_dimension: int,
    thumbnail: bool = False,
) -> dict[str, Any]:
    processed = ImageOps.exif_transpose(image.copy())
    processed.load()
    processed.thumbnail((max_dimension, max_dimension), pil_resample_filter())
    has_alpha = image_has_alpha(processed)

    if thumbnail:
        output_format = "PNG" if has_alpha else "JPEG"
    elif source_mime_type == "image/jpeg":
        output_format = "JPEG"
    elif source_mime_type == "image/webp":
        output_format = "WEBP"
    elif source_mime_type == "image/gif":
        output_format = "GIF"
    else:
        output_format = "PNG"

    if output_format == "JPEG":
        encoded = save_pillow_image(
            processed.convert("RGB"),
            "JPEG",
            quality=JPEG_QUALITY if not thumbnail else 78,
            optimize=True,
            progressive=True,
        )
        mime_type, extension = "image/jpeg", "jpg"
    elif output_format == "WEBP":
        encoded = save_pillow_image(
            processed.convert("RGBA" if has_alpha else "RGB"),
            "WEBP",
            quality=WEBP_QUALITY if not thumbnail else 78,
            method=6,
        )
        mime_type, extension = "image/webp", "webp"
    elif output_format == "GIF":
        encoded = save_pillow_image(
            processed.convert("P", palette=pil_adaptive_palette()),
            "GIF",
            optimize=True,
        )
        mime_type, extension = "image/gif", "gif"
    else:
        mode = "RGBA" if has_alpha else "RGB"
        encoded = save_pillow_image(processed.convert(mode), "PNG", optimize=True)
        mime_type, extension = "image/png", "png"

    return {
        "bytes": encoded,
        "mime_type": mime_type,
        "extension": extension,
        "width": processed.width,
        "height": processed.height,
    }


def encode_animated_image(
    image: Any,
    *,
    source_mime_type: str,
    max_dimension: int,
) -> dict[str, Any]:
    output_format = "WEBP" if source_mime_type == "image/webp" else "GIF"
    frames = []
    durations = []
    for frame in ImageSequence.Iterator(image):
        duration = int(frame.info.get("duration", image.info.get("duration", 80)) or 80)
        processed = frame.copy().convert("RGBA")
        processed.thumbnail((max_dimension, max_dimension), pil_resample_filter())
        frames.append(processed)
        durations.append(duration)
    if not frames:
        raise APIError("Could not read that animated image.")

    buffer = BytesIO()
    if output_format == "WEBP":
        first = frames[0]
        first.save(
            buffer,
            format="WEBP",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=int(image.info.get("loop", 0) or 0),
            quality=WEBP_QUALITY,
            method=6,
        )
        mime_type, extension = "image/webp", "webp"
    else:
        palette_frames = [frame.convert("P", palette=pil_adaptive_palette()) for frame in frames]
        first = palette_frames[0]
        first.save(
            buffer,
            format="GIF",
            save_all=True,
            append_images=palette_frames[1:],
            duration=durations,
            loop=int(image.info.get("loop", 0) or 0),
            disposal=2,
            optimize=True,
        )
        mime_type, extension = "image/gif", "gif"

    return {
        "bytes": buffer.getvalue(),
        "mime_type": mime_type,
        "extension": extension,
        "width": frames[0].width,
        "height": frames[0].height,
    }


def process_image_upload_bytes(
    binary: bytes,
    *,
    mime_type: str,
    extension: str,
    field: str,
    kind: str,
) -> dict[str, Any]:
    if not PIL_AVAILABLE:
        return {
            "bytes": binary,
            "mime_type": mime_type,
            "extension": extension,
            "thumbnail_bytes": b"",
            "thumbnail_mime_type": "",
            "thumbnail_extension": "",
            "processed": False,
        }

    max_dimension = AVATAR_IMAGE_MAX_DIMENSION if kind == "avatar" else POST_IMAGE_MAX_DIMENSION
    try:
        with Image.open(BytesIO(binary)) as image:
            image.load() if not getattr(image, "is_animated", False) else None
            is_animated = bool(getattr(image, "is_animated", False))
            if is_animated:
                full = encode_animated_image(
                    image,
                    source_mime_type=mime_type,
                    max_dimension=max_dimension,
                )
                first_frame = next(ImageSequence.Iterator(image)).copy()
                thumb = encode_static_image(
                    first_frame,
                    source_mime_type="image/png",
                    max_dimension=POST_THUMBNAIL_MAX_DIMENSION,
                    thumbnail=True,
                )
            else:
                full = encode_static_image(
                    image,
                    source_mime_type=mime_type,
                    max_dimension=max_dimension,
                )
                thumb = encode_static_image(
                    image,
                    source_mime_type=mime_type,
                    max_dimension=POST_THUMBNAIL_MAX_DIMENSION,
                    thumbnail=True,
                )
    except (UnidentifiedImageError, OSError, ValueError, EOFError) as exc:
        raise APIError(f"{field} could not be processed as a safe image.") from exc

    result = {
        **full,
        "thumbnail_bytes": b"",
        "thumbnail_mime_type": "",
        "thumbnail_extension": "",
        "processed": True,
    }
    if kind == "post":
        result.update(
            {
                "thumbnail_bytes": thumb["bytes"],
                "thumbnail_mime_type": thumb["mime_type"],
                "thumbnail_extension": thumb["extension"],
            }
        )
    return result


def decode_image_upload(
    payload: Any,
    *,
    field: str,
    max_bytes: int,
    kind: str = "post",
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise APIError(f"{field} upload is invalid.")
    data_url = str(payload.get("dataUrl") or "")
    if not data_url.startswith("data:"):
        raise APIError(f"{field} upload is missing file data.")
    try:
        header, encoded = data_url.split(",", 1)
    except ValueError as exc:
        raise APIError(f"{field} upload is malformed.") from exc
    if ";base64" not in header:
        raise APIError(f"{field} upload is malformed.")
    try:
        binary = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise APIError(f"{field} upload could not be decoded.") from exc
    if not binary:
        raise APIError(f"{field} upload is empty.")
    if len(binary) > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        raise APIError(f"{field} must stay under {max_mb:.0f}MB.")
    mime_type, extension = detect_image_type(binary)
    width, height = validate_image_geometry(binary, mime_type, field=field)
    processed = process_image_upload_bytes(
        binary,
        mime_type=mime_type,
        extension=extension,
        field=field,
        kind=kind,
    )
    filename = Path(str(payload.get("name") or payload.get("filename") or "")).name.strip()
    if not filename:
        filename = f"{slugify_text(field, fallback='image')}.{processed['extension']}"
    alt_text = clean_text(
        payload.get("alt") or Path(filename).stem.replace("-", " ").replace("_", " "),
        min_len=0,
        max_len=120,
        field=f"{field} description",
    )
    return {
        "bytes": processed["bytes"],
        "mime_type": processed["mime_type"],
        "extension": processed["extension"],
        "thumbnail_bytes": processed.get("thumbnail_bytes") or b"",
        "thumbnail_mime_type": processed.get("thumbnail_mime_type") or "",
        "thumbnail_extension": processed.get("thumbnail_extension") or "",
        "filename": filename,
        "alt_text": alt_text or "Forum image",
        "width": processed.get("width") or width,
        "height": processed.get("height") or height,
        "original_width": width,
        "original_height": height,
        "processed": bool(processed.get("processed")),
    }


def normalize_media_uploads(
    value: Any,
    *,
    max_items: int,
    field: str = "Images",
    max_bytes: int = POST_MEDIA_MAX_BYTES,
    kind: str = "post",
) -> list[dict[str, Any]]:
    if value is None or value == "":
        return []
    if not isinstance(value, list):
        raise APIError(f"{field} must be sent as a list.")
    if len(value) > max_items:
        raise APIError(f"You can attach up to {max_items} images per post.")
    return [
        decode_image_upload(item, field=f"{field} #{index}", max_bytes=max_bytes, kind=kind)
        for index, item in enumerate(value, start=1)
    ]
