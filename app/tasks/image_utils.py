"""
Shared image utilities for download, upload, and conversion.
"""

import base64
import os
from io import BytesIO
from typing import Optional, Tuple

import httpx
from PIL import Image


KIOSK_UPLOAD_URL = os.environ.get("KIOSK_UPLOAD_URL", "")
KIOSK_API_KEY = os.environ.get("KIOSK_API_KEY", "")

SUPPORTED_FORMATS = {"png", "jpeg", "jpg", "webp", "bmp", "tiff", "gif"}
FORMAT_MIMETYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "gif": "image/gif",
}


async def download_image(url: str, timeout: float = 30.0) -> bytes:
    """Download image from URL, return raw bytes."""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


def decode_base64_image(b64: str) -> bytes:
    """Decode base64 string to raw bytes. Handles data URI prefix."""
    if "," in b64 and b64.startswith("data:"):
        b64 = b64.split(",", 1)[1]
    return base64.b64decode(b64)


async def resolve_image(
    image_base64: Optional[str] = None,
    image_url: Optional[str] = None,
) -> Image.Image:
    """
    Resolve an image from either base64 or URL input.
    Returns a PIL Image. Raises ValueError if neither provided.
    """
    if image_url:
        raw = await download_image(image_url)
        return Image.open(BytesIO(raw))
    elif image_base64:
        raw = decode_base64_image(image_base64)
        return Image.open(BytesIO(raw))
    else:
        raise ValueError("Must provide either image_base64 or image_url")


async def resolve_image_bytes(
    image_base64: Optional[str] = None,
    image_url: Optional[str] = None,
) -> bytes:
    """Resolve image input to raw bytes."""
    if image_url:
        return await download_image(image_url)
    elif image_base64:
        return decode_base64_image(image_base64)
    else:
        raise ValueError("Must provide either image_base64 or image_url")


def image_to_bytes(
    img: Image.Image,
    fmt: str = "png",
    quality: int = 85,
) -> bytes:
    """Convert PIL Image to bytes in specified format."""
    buf = BytesIO()
    save_fmt = fmt.upper()
    if save_fmt == "JPG":
        save_fmt = "JPEG"

    # Handle RGBA → RGB for formats that don't support alpha
    if save_fmt in ("JPEG", "BMP") and img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    kwargs = {}
    if save_fmt == "JPEG":
        kwargs["quality"] = quality
    elif save_fmt == "WEBP":
        kwargs["quality"] = quality

    img.save(buf, format=save_fmt, **kwargs)
    return buf.getvalue()


def image_to_base64(
    img: Image.Image,
    fmt: str = "png",
    quality: int = 85,
) -> str:
    """Convert PIL Image to base64 string."""
    raw = image_to_bytes(img, fmt, quality)
    return base64.b64encode(raw).decode("utf-8")


def get_image_info(img: Image.Image) -> dict:
    """Extract metadata from a PIL Image."""
    return {
        "width": img.width,
        "height": img.height,
        "mode": img.mode,
        "format": img.format or "unknown",
    }


async def upload_to_kiosk(
    image_data: bytes,
    filename: str,
    mime_type: str = "image/png",
    bucket: str = "temp",
) -> Optional[str]:
    """
    Upload image bytes to Kiosk via the kiosk-stock n8n webhook.
    Sends base64-encoded content as JSON. Returns the public URL.
    Returns None if Kiosk is not configured.
    """
    if not KIOSK_UPLOAD_URL or not KIOSK_API_KEY:
        return None

    import uuid
    unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
    path = f"image-tools/{unique_name}"
    file_content = base64.b64encode(image_data).decode("utf-8")

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            KIOSK_UPLOAD_URL,
            json={"bucket": bucket, "path": path, "file_content": file_content},
            headers={"Authorization": f"Bearer {KIOSK_API_KEY}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("url") or data.get("public_url")


async def process_and_respond(
    img: Image.Image,
    fmt: str = "png",
    quality: int = 85,
    filename_prefix: str = "image",
) -> dict:
    """
    Standard response pipeline: convert image → upload to Kiosk → return URL or base64.
    """
    raw = image_to_bytes(img, fmt, quality)
    mime = FORMAT_MIMETYPES.get(fmt.lower(), "image/png")
    ext = fmt.lower()
    if ext == "jpeg":
        ext = "jpg"

    filename = f"{filename_prefix}.{ext}"

    url = await upload_to_kiosk(raw, filename, mime)

    return {
        "url": url,
        "image_base64": base64.b64encode(raw).decode("utf-8") if not url else None,
        "width": img.width,
        "height": img.height,
        "format": fmt.lower(),
        "size_bytes": len(raw),
    }
