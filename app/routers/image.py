"""
Image processing endpoints — resize, crop, rotate, flip, convert, compress,
montage, grid-overlay, watermark, adjust, thumbnail, info.

All endpoints accept either image_base64 or image_url as input.
When Kiosk is configured, results are uploaded and a URL is returned.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

from app.tasks.grid_overlay import process_base64, get_ux_review_prompt, GRID_PROMPT_PREFIX
from app.tasks.image_utils import (
    resolve_image,
    resolve_image_bytes,
    decode_base64_image,
    image_to_base64,
    image_to_bytes,
    get_image_info,
    process_and_respond,
    upload_to_kiosk,
    FORMAT_MIMETYPES,
)

router = APIRouter(prefix="/image", tags=["image"])


# ---------------------------------------------------------------------------
# /image/upload — upload base64 image to Kiosk, return URL
# ---------------------------------------------------------------------------

class UploadRequest(BaseModel):
    image_base64: str = Field(..., description="Base64-encoded image data")
    filename: Optional[str] = Field(None, description="Desired filename (auto-generated if omitted)")
    bucket: str = Field(default="temp", pattern="^(temp|public|restricted)$", description="Kiosk bucket: temp (24h), public (permanent), restricted")


class UploadResponse(BaseModel):
    url: str = Field(description="Kiosk URL for the uploaded image")
    filename: str
    bucket: str


@router.post("/upload", response_model=UploadResponse)
async def upload_image(request: UploadRequest) -> UploadResponse:
    """
    Upload a base64-encoded image to Kiosk and return the URL.
    Use this to make local files available to other image-tools operations.
    """
    try:
        image_bytes = decode_base64_image(request.image_base64)

        # Detect format for mime type
        from PIL import Image as PILImage
        from io import BytesIO
        img = PILImage.open(BytesIO(image_bytes))
        fmt = (img.format or "PNG").lower()
        mime = FORMAT_MIMETYPES.get(fmt, "image/png")
        ext = fmt if fmt != "jpeg" else "jpg"

        import uuid
        filename = request.filename or f"upload-{uuid.uuid4().hex[:8]}.{ext}"

        url = await upload_to_kiosk(image_bytes, filename, mime, request.bucket)
        if not url:
            raise HTTPException(status_code=500, detail="Kiosk not configured (KIOSK_UPLOAD_URL / KIOSK_API_KEY)")

        return UploadResponse(url=url, filename=filename, bucket=request.bucket)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Upload failed: {e}")


# ---------------------------------------------------------------------------
# Shared base models
# ---------------------------------------------------------------------------

class ImageInput(BaseModel):
    """Base input supporting both base64 and URL."""
    image_base64: Optional[str] = Field(None, description="Base64-encoded input image")
    image_url: Optional[str] = Field(None, description="URL to download input image from")


class ImageOutput(BaseModel):
    """Standard image output."""
    url: Optional[str] = Field(None, description="Kiosk URL (when configured)")
    image_base64: Optional[str] = Field(None, description="Base64-encoded output (fallback when no Kiosk)")
    width: int
    height: int
    format: str
    size_bytes: int


# ---------------------------------------------------------------------------
# /image/info
# ---------------------------------------------------------------------------

class InfoRequest(ImageInput):
    pass


class InfoResponse(BaseModel):
    width: int
    height: int
    mode: str
    format: str


@router.post("/info", response_model=InfoResponse)
async def image_info(request: InfoRequest) -> InfoResponse:
    """Get image metadata (dimensions, mode, format)."""
    try:
        img = await resolve_image(request.image_base64, request.image_url)
        info = get_image_info(img)
        return InfoResponse(**info)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read image: {e}")


# ---------------------------------------------------------------------------
# /image/resize
# ---------------------------------------------------------------------------

class ResizeRequest(ImageInput):
    width: Optional[int] = Field(None, ge=1, le=8192, description="Target width")
    height: Optional[int] = Field(None, ge=1, le=8192, description="Target height")
    max_dimension: Optional[int] = Field(None, ge=1, le=8192, description="Max width or height (preserves aspect)")
    output_format: str = Field(default="png", pattern="^(png|jpeg|jpg|webp)$")
    quality: int = Field(default=85, ge=1, le=100)


@router.post("/resize", response_model=ImageOutput)
async def resize_image(request: ResizeRequest) -> ImageOutput:
    """Resize image with aspect ratio preservation options."""
    try:
        img = await resolve_image(request.image_base64, request.image_url)
        orig_w, orig_h = img.size

        if request.max_dimension:
            ratio = min(request.max_dimension / orig_w, request.max_dimension / orig_h)
            new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
        elif request.width and request.height:
            new_w, new_h = request.width, request.height
        elif request.width:
            ratio = request.width / orig_w
            new_w, new_h = request.width, int(orig_h * ratio)
        elif request.height:
            ratio = request.height / orig_h
            new_w, new_h = int(orig_w * ratio), request.height
        else:
            raise HTTPException(status_code=400, detail="Provide width, height, or max_dimension")

        from PIL import Image as PILImage
        result = img.resize((new_w, new_h), PILImage.Resampling.LANCZOS)
        return ImageOutput(**await process_and_respond(result, request.output_format, request.quality, "resized"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Resize failed: {e}")


# ---------------------------------------------------------------------------
# /image/crop
# ---------------------------------------------------------------------------

class CropRequest(ImageInput):
    x: int = Field(0, ge=0, description="Left offset in pixels")
    y: int = Field(0, ge=0, description="Top offset in pixels")
    width: int = Field(..., ge=1, description="Crop width")
    height: int = Field(..., ge=1, description="Crop height")
    output_format: str = Field(default="png", pattern="^(png|jpeg|jpg|webp)$")
    quality: int = Field(default=85, ge=1, le=100)


@router.post("/crop", response_model=ImageOutput)
async def crop_image(request: CropRequest) -> ImageOutput:
    """Crop a region from the image."""
    try:
        img = await resolve_image(request.image_base64, request.image_url)
        box = (request.x, request.y, request.x + request.width, request.y + request.height)

        if box[2] > img.width or box[3] > img.height:
            raise HTTPException(status_code=400, detail="Crop region exceeds image dimensions")

        result = img.crop(box)
        return ImageOutput(**await process_and_respond(result, request.output_format, request.quality, "cropped"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Crop failed: {e}")


# ---------------------------------------------------------------------------
# /image/rotate
# ---------------------------------------------------------------------------

class RotateRequest(ImageInput):
    angle: float = Field(..., description="Rotation angle in degrees (counterclockwise)")
    expand: bool = Field(default=True, description="Expand canvas to fit rotated image")
    fill_color: str = Field(default="#FFFFFF", description="Background fill color (hex)")
    output_format: str = Field(default="png", pattern="^(png|jpeg|jpg|webp)$")
    quality: int = Field(default=85, ge=1, le=100)


@router.post("/rotate", response_model=ImageOutput)
async def rotate_image(request: RotateRequest) -> ImageOutput:
    """Rotate image by arbitrary angle."""
    try:
        img = await resolve_image(request.image_base64, request.image_url)
        hex_color = request.fill_color.lstrip("#")
        fill = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        if img.mode == "RGBA":
            fill = fill + (255,)

        result = img.rotate(request.angle, expand=request.expand, fillcolor=fill, resample=3)
        return ImageOutput(**await process_and_respond(result, request.output_format, request.quality, "rotated"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Rotate failed: {e}")


# ---------------------------------------------------------------------------
# /image/flip
# ---------------------------------------------------------------------------

class FlipRequest(ImageInput):
    direction: str = Field(..., pattern="^(horizontal|vertical)$", description="Flip direction")
    output_format: str = Field(default="png", pattern="^(png|jpeg|jpg|webp)$")
    quality: int = Field(default=85, ge=1, le=100)


@router.post("/flip", response_model=ImageOutput)
async def flip_image(request: FlipRequest) -> ImageOutput:
    """Flip image horizontally or vertically."""
    try:
        from PIL import ImageOps
        img = await resolve_image(request.image_base64, request.image_url)

        if request.direction == "horizontal":
            result = ImageOps.mirror(img)
        else:
            result = ImageOps.flip(img)

        return ImageOutput(**await process_and_respond(result, request.output_format, request.quality, "flipped"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Flip failed: {e}")


# ---------------------------------------------------------------------------
# /image/convert
# ---------------------------------------------------------------------------

class ConvertRequest(ImageInput):
    output_format: str = Field(..., pattern="^(png|jpeg|jpg|webp|bmp|tiff|gif)$", description="Target format")
    quality: int = Field(default=85, ge=1, le=100, description="Quality for JPEG/WebP")


@router.post("/convert", response_model=ImageOutput)
async def convert_image(request: ConvertRequest) -> ImageOutput:
    """Convert image to a different format."""
    try:
        img = await resolve_image(request.image_base64, request.image_url)
        return ImageOutput(**await process_and_respond(img, request.output_format, request.quality, "converted"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Convert failed: {e}")


# ---------------------------------------------------------------------------
# /image/compress
# ---------------------------------------------------------------------------

class CompressRequest(ImageInput):
    target_format: str = Field(default="webp", pattern="^(jpeg|jpg|webp|png)$", description="Output format")
    quality: int = Field(default=80, ge=1, le=100, description="Compression quality")
    max_dimension: Optional[int] = Field(None, ge=1, le=8192, description="Downscale if larger")
    strip_exif: bool = Field(default=True, description="Remove EXIF metadata")


class CompressResponse(ImageOutput):
    original_size_bytes: int
    compression_ratio: float


@router.post("/compress", response_model=CompressResponse)
async def compress_image(request: CompressRequest) -> CompressResponse:
    """Compress/optimize image for web delivery."""
    try:
        raw_input = await resolve_image_bytes(request.image_base64, request.image_url)
        original_size = len(raw_input)

        from PIL import Image as PILImage
        from io import BytesIO
        img = PILImage.open(BytesIO(raw_input))

        if request.max_dimension:
            ratio = min(request.max_dimension / img.width, request.max_dimension / img.height)
            if ratio < 1:
                new_w, new_h = int(img.width * ratio), int(img.height * ratio)
                img = img.resize((new_w, new_h), PILImage.Resampling.LANCZOS)

        resp = await process_and_respond(img, request.target_format, request.quality, "compressed")
        resp["original_size_bytes"] = original_size
        resp["compression_ratio"] = round(resp["size_bytes"] / original_size, 3) if original_size > 0 else 1.0
        return CompressResponse(**resp)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Compress failed: {e}")


# ---------------------------------------------------------------------------
# /image/watermark
# ---------------------------------------------------------------------------

class WatermarkRequest(ImageInput):
    text: str = Field(..., max_length=200, description="Watermark text")
    position: str = Field(default="bottom-right", pattern="^(top-left|top-right|bottom-left|bottom-right|center)$")
    font_size: int = Field(default=24, ge=8, le=200)
    opacity: float = Field(default=0.5, ge=0.1, le=1.0)
    color: str = Field(default="#FFFFFF", description="Text color (hex)")
    output_format: str = Field(default="png", pattern="^(png|jpeg|jpg|webp)$")
    quality: int = Field(default=85, ge=1, le=100)


@router.post("/watermark", response_model=ImageOutput)
async def watermark_image(request: WatermarkRequest) -> ImageOutput:
    """Add text watermark to image."""
    try:
        from PIL import Image as PILImage, ImageDraw, ImageFont
        img = await resolve_image(request.image_base64, request.image_url)

        if img.mode != "RGBA":
            img = img.convert("RGBA")

        overlay = PILImage.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", request.font_size)
        except OSError:
            font = ImageFont.load_default(size=request.font_size)

        hex_c = request.color.lstrip("#")
        r, g, b = (int(hex_c[i:i+2], 16) for i in (0, 2, 4))
        alpha = int(255 * request.opacity)
        fill = (r, g, b, alpha)

        bbox = draw.textbbox((0, 0), request.text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        padding = 20

        positions = {
            "top-left": (padding, padding),
            "top-right": (img.width - tw - padding, padding),
            "bottom-left": (padding, img.height - th - padding),
            "bottom-right": (img.width - tw - padding, img.height - th - padding),
            "center": ((img.width - tw) // 2, (img.height - th) // 2),
        }
        pos = positions[request.position]

        draw.text(pos, request.text, font=font, fill=fill)
        result = PILImage.alpha_composite(img, overlay)

        if request.output_format.lower() in ("jpeg", "jpg"):
            result = result.convert("RGB")

        return ImageOutput(**await process_and_respond(result, request.output_format, request.quality, "watermarked"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Watermark failed: {e}")


# ---------------------------------------------------------------------------
# /image/adjust
# ---------------------------------------------------------------------------

class AdjustRequest(ImageInput):
    brightness: float = Field(default=1.0, ge=0.0, le=3.0, description="Brightness factor (1.0 = unchanged)")
    contrast: float = Field(default=1.0, ge=0.0, le=3.0, description="Contrast factor (1.0 = unchanged)")
    saturation: float = Field(default=1.0, ge=0.0, le=3.0, description="Saturation factor (1.0 = unchanged)")
    sharpness: float = Field(default=1.0, ge=0.0, le=3.0, description="Sharpness factor (1.0 = unchanged)")
    output_format: str = Field(default="png", pattern="^(png|jpeg|jpg|webp)$")
    quality: int = Field(default=85, ge=1, le=100)


@router.post("/adjust", response_model=ImageOutput)
async def adjust_image(request: AdjustRequest) -> ImageOutput:
    """Adjust brightness, contrast, saturation, and sharpness."""
    try:
        from PIL import ImageEnhance
        img = await resolve_image(request.image_base64, request.image_url)

        if request.brightness != 1.0:
            img = ImageEnhance.Brightness(img).enhance(request.brightness)
        if request.contrast != 1.0:
            img = ImageEnhance.Contrast(img).enhance(request.contrast)
        if request.saturation != 1.0:
            img = ImageEnhance.Color(img).enhance(request.saturation)
        if request.sharpness != 1.0:
            img = ImageEnhance.Sharpness(img).enhance(request.sharpness)

        return ImageOutput(**await process_and_respond(img, request.output_format, request.quality, "adjusted"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Adjust failed: {e}")


# ---------------------------------------------------------------------------
# /image/thumbnail
# ---------------------------------------------------------------------------

class ThumbnailRequest(ImageInput):
    size: int = Field(default=256, ge=16, le=1024, description="Max dimension for thumbnail")
    output_format: str = Field(default="webp", pattern="^(png|jpeg|jpg|webp)$")
    quality: int = Field(default=80, ge=1, le=100)


@router.post("/thumbnail", response_model=ImageOutput)
async def create_thumbnail(request: ThumbnailRequest) -> ImageOutput:
    """Generate optimized thumbnail."""
    try:
        img = await resolve_image(request.image_base64, request.image_url)
        img.thumbnail((request.size, request.size))
        return ImageOutput(**await process_and_respond(img, request.output_format, request.quality, "thumbnail"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Thumbnail failed: {e}")


# ---------------------------------------------------------------------------
# /image/montage (updated with URL support)
# ---------------------------------------------------------------------------

class MontageRequest(BaseModel):
    images: Optional[List[str]] = Field(None, description="Array of base64-encoded images")
    image_urls: Optional[object] = Field(None, description="Array of image URLs (accepts JSON array or stringified JSON)")
    columns: Optional[int] = Field(None, ge=1, le=10)
    spacing: int = Field(default=10, ge=0, le=100)
    background_color: str = Field(default="#FFFFFF")
    labels: Optional[List[str]] = Field(None)
    label_position: str = Field(default="bottom", pattern="^(top|bottom)$")
    max_cell_width: Optional[int] = Field(None, ge=50, le=2048)
    output_format: str = Field(default="png", pattern="^(png|jpeg|jpg|webp)$")
    quality: int = Field(default=85, ge=1, le=100)


@router.post("/montage", response_model=ImageOutput)
async def create_montage(request: MontageRequest) -> ImageOutput:
    """Combine multiple images into a grid/montage layout."""
    from PIL import Image as PILImage, ImageDraw, ImageFont
    from io import BytesIO
    import base64
    import json
    import math

    try:
        # Flexibly parse image_urls — handles string, list, or stringified JSON
        url_list = None
        if request.image_urls is not None:
            if isinstance(request.image_urls, list):
                url_list = request.image_urls
            elif isinstance(request.image_urls, str):
                try:
                    parsed = json.loads(request.image_urls)
                    if isinstance(parsed, list):
                        url_list = parsed
                except (json.JSONDecodeError, TypeError):
                    url_list = [u.strip() for u in request.image_urls.split(",") if u.strip()]

        source_list = url_list or request.images
        if not source_list or len(source_list) < 2:
            raise HTTPException(status_code=400, detail="Provide at least 2 images via images or image_urls")

        pil_images = []
        is_urls = url_list is not None
        for i, src in enumerate(source_list):
            try:
                if is_urls:
                    img = await resolve_image(image_url=src)
                else:
                    img = await resolve_image(image_base64=src)
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                pil_images.append(img)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to load image {i}: {e}")

        n = len(pil_images)
        cols = request.columns or math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)

        max_w = max(im.width for im in pil_images)
        max_h = max(im.height for im in pil_images)

        if request.max_cell_width and max_w > request.max_cell_width:
            scale = request.max_cell_width / max_w
            max_w = request.max_cell_width
            max_h = int(max_h * scale)
            pil_images = [
                im.resize((int(im.width * scale), int(im.height * scale)), PILImage.Resampling.LANCZOS)
                for im in pil_images
            ]

        label_height = 25 if request.labels else 0
        cell_w = max_w + request.spacing
        cell_h = max_h + request.spacing + label_height
        canvas_w = cols * cell_w + request.spacing
        canvas_h = rows * cell_h + request.spacing

        bg_hex = request.background_color.lstrip("#")
        bg_rgb = tuple(int(bg_hex[i:i+2], 16) for i in (0, 2, 4))
        canvas = PILImage.new("RGB", (canvas_w, canvas_h), bg_rgb)

        font = None
        if request.labels:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            except OSError:
                font = ImageFont.load_default()

        draw = ImageDraw.Draw(canvas) if request.labels else None

        for i, im in enumerate(pil_images):
            row, col = divmod(i, cols)
            x = col * cell_w + request.spacing + (max_w - im.width) // 2
            y = row * cell_h + request.spacing
            if request.label_position == "top" and request.labels:
                y += label_height

            if im.mode == "RGBA":
                canvas.paste(im, (x, y), im)
            else:
                canvas.paste(im, (x, y))

            if request.labels and i < len(request.labels) and draw and font:
                label = request.labels[i]
                label_x = col * cell_w + request.spacing + max_w // 2
                label_y = (y + im.height + 5) if request.label_position == "bottom" else (row * cell_h + request.spacing + 5)
                bbox = draw.textbbox((0, 0), label, font=font)
                tw = bbox[2] - bbox[0]
                draw.text((label_x - tw // 2, label_y), label, fill=(0, 0, 0), font=font)

        resp = await process_and_respond(canvas, request.output_format, request.quality, "montage")
        return ImageOutput(**resp)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Montage failed: {e}")


# ---------------------------------------------------------------------------
# /image/grid-overlay (updated with URL support)
# ---------------------------------------------------------------------------

class GridOverlayRequest(ImageInput):
    grid_size: int = Field(default=9, ge=2, le=26)
    alpha: float = Field(default=0.3, ge=0.1, le=1.0)
    margin: int = Field(default=15, ge=5, le=50)
    output_format: str = Field(default="png", pattern="^(png|jpeg|jpg)$")
    include_prompt: bool = Field(default=False)


class GridOverlayResponse(BaseModel):
    url: Optional[str] = None
    image_base64: Optional[str] = None
    prompt_prefix: Optional[str] = None
    ux_review_prompt: Optional[str] = None


@router.post("/grid-overlay", response_model=GridOverlayResponse)
async def grid_overlay(request: GridOverlayRequest) -> GridOverlayResponse:
    """Add a reference grid overlay to an image for AI vision analysis."""
    try:
        # Resolve input to base64 (grid_overlay module expects base64)
        if request.image_url and not request.image_base64:
            raw = await resolve_image_bytes(image_url=request.image_url)
            import base64
            b64_input = base64.b64encode(raw).decode("utf-8")
        else:
            b64_input = request.image_base64

        if not b64_input:
            raise HTTPException(status_code=400, detail="Provide image_base64 or image_url")

        result_b64 = process_base64(
            image_base64=b64_input,
            grid_size=request.grid_size,
            alpha=request.alpha,
            margin=request.margin,
            output_format=request.output_format,
        )

        response = GridOverlayResponse(image_base64=result_b64)
        if request.include_prompt:
            response.prompt_prefix = GRID_PROMPT_PREFIX
            response.ux_review_prompt = get_ux_review_prompt()

        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Grid overlay failed: {e}")
