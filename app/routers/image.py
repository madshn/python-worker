"""
Image processing endpoints.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

from app.tasks.grid_overlay import process_base64, get_ux_review_prompt, GRID_PROMPT_PREFIX


router = APIRouter(prefix="/image", tags=["image"])


class GridOverlayRequest(BaseModel):
    """Request model for grid overlay endpoint."""
    image_base64: str = Field(..., description="Base64-encoded input image")
    grid_size: int = Field(default=9, ge=2, le=26, description="Grid divisions (2-26)")
    alpha: float = Field(default=0.3, ge=0.1, le=1.0, description="Grid line opacity")
    margin: int = Field(default=15, ge=5, le=50, description="Label margin in pixels")
    output_format: str = Field(default="png", pattern="^(png|jpeg|jpg)$", description="Output format")
    include_prompt: bool = Field(default=False, description="Include UX review prompt in response")


class GridOverlayResponse(BaseModel):
    """Response model for grid overlay endpoint."""
    image_base64: str = Field(..., description="Base64-encoded output image with grid")
    prompt_prefix: Optional[str] = Field(None, description="Prompt prefix for LLM (if requested)")
    ux_review_prompt: Optional[str] = Field(None, description="Full UX review prompt (if requested)")


@router.post("/grid-overlay", response_model=GridOverlayResponse)
async def grid_overlay(request: GridOverlayRequest) -> GridOverlayResponse:
    """
    Add a reference grid overlay to an image for AI vision analysis.

    The grid divides the image into a matrix with chess-style labels (A-I columns, 1-9 rows).
    Useful for spatial references when reviewing screenshots with vision LLMs.

    Based on Grid-Augmented Vision research (arXiv:2411.18270).
    """
    try:
        result_base64 = process_base64(
            image_base64=request.image_base64,
            grid_size=request.grid_size,
            alpha=request.alpha,
            margin=request.margin,
            output_format=request.output_format,
        )

        response = GridOverlayResponse(image_base64=result_base64)

        if request.include_prompt:
            response.prompt_prefix = GRID_PROMPT_PREFIX
            response.ux_review_prompt = get_ux_review_prompt()

        return response

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image processing failed: {str(e)}")


class ResizeRequest(BaseModel):
    """Request model for resize endpoint."""
    image_base64: str = Field(..., description="Base64-encoded input image")
    width: Optional[int] = Field(None, ge=1, le=4096, description="Target width (preserves aspect if only one dimension)")
    height: Optional[int] = Field(None, ge=1, le=4096, description="Target height (preserves aspect if only one dimension)")
    max_dimension: Optional[int] = Field(None, ge=1, le=4096, description="Max width or height (preserves aspect)")
    output_format: str = Field(default="png", pattern="^(png|jpeg|jpg)$", description="Output format")
    quality: int = Field(default=85, ge=1, le=100, description="JPEG quality (if jpeg format)")


class ResizeResponse(BaseModel):
    """Response model for resize endpoint."""
    image_base64: str = Field(..., description="Base64-encoded resized image")
    width: int = Field(..., description="Output width")
    height: int = Field(..., description="Output height")


@router.post("/resize", response_model=ResizeResponse)
async def resize_image(request: ResizeRequest) -> ResizeResponse:
    """
    Resize an image with various options.

    Provide width and/or height for exact dimensions, or max_dimension to limit size while preserving aspect ratio.
    """
    from PIL import Image
    from io import BytesIO
    import base64

    try:
        # Decode input
        image_data = base64.b64decode(request.image_base64)
        img = Image.open(BytesIO(image_data))
        orig_w, orig_h = img.size

        # Calculate target dimensions
        if request.max_dimension:
            # Scale to fit within max_dimension
            ratio = min(request.max_dimension / orig_w, request.max_dimension / orig_h)
            new_w = int(orig_w * ratio)
            new_h = int(orig_h * ratio)
        elif request.width and request.height:
            # Exact dimensions
            new_w, new_h = request.width, request.height
        elif request.width:
            # Scale by width, preserve aspect
            ratio = request.width / orig_w
            new_w = request.width
            new_h = int(orig_h * ratio)
        elif request.height:
            # Scale by height, preserve aspect
            ratio = request.height / orig_h
            new_w = int(orig_w * ratio)
            new_h = request.height
        else:
            raise HTTPException(status_code=400, detail="Must provide width, height, or max_dimension")

        # Resize
        result = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Convert to RGB if saving as JPEG
        if request.output_format.lower() in ['jpg', 'jpeg']:
            if result.mode in ('RGBA', 'P'):
                result = result.convert('RGB')

        # Encode output
        buffer = BytesIO()
        save_kwargs = {}
        if request.output_format.lower() in ['jpg', 'jpeg']:
            save_kwargs['quality'] = request.quality
        result.save(buffer, format=request.output_format.upper(), **save_kwargs)

        return ResizeResponse(
            image_base64=base64.b64encode(buffer.getvalue()).decode('utf-8'),
            width=new_w,
            height=new_h,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Resize failed: {str(e)}")


class MontageRequest(BaseModel):
    """Request model for montage/composite endpoint."""
    images: List[str] = Field(..., min_length=2, max_length=25, description="Array of base64-encoded images")
    columns: Optional[int] = Field(None, ge=1, le=10, description="Number of columns (auto-calculated if not provided)")
    spacing: int = Field(default=10, ge=0, le=100, description="Spacing between images in pixels")
    background_color: str = Field(default="#FFFFFF", description="Background color (hex)")
    labels: Optional[List[str]] = Field(None, description="Optional labels for each image")
    label_position: str = Field(default="bottom", pattern="^(top|bottom)$", description="Label position")
    max_cell_width: Optional[int] = Field(None, ge=50, le=2048, description="Max width per cell (scales down if needed)")
    output_format: str = Field(default="png", pattern="^(png|jpeg|jpg)$", description="Output format")


class MontageResponse(BaseModel):
    """Response model for montage endpoint."""
    image_base64: str = Field(..., description="Base64-encoded montage image")
    width: int = Field(..., description="Output width")
    height: int = Field(..., description="Output height")
    grid: str = Field(..., description="Grid dimensions (e.g., '3x2')")


@router.post("/montage", response_model=MontageResponse)
async def create_montage(request: MontageRequest) -> MontageResponse:
    """
    Combine multiple images into a grid/montage layout.

    Useful for:
    - Character reference sheets (maintaining consistency across generations)
    - Before/after comparisons
    - Multi-image context for vision LLMs
    - Contact sheets for review
    """
    from PIL import Image, ImageDraw, ImageFont
    from io import BytesIO
    import base64
    import math

    try:
        # Decode all images
        images = []
        for i, img_b64 in enumerate(request.images):
            try:
                img_data = base64.b64decode(img_b64)
                img = Image.open(BytesIO(img_data))
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                images.append(img)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to decode image {i}: {str(e)}")

        # Calculate grid dimensions
        n = len(images)
        if request.columns:
            cols = request.columns
        else:
            # Auto-calculate: prefer roughly square grids
            cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)

        # Find max dimensions (or use max_cell_width to constrain)
        max_w = max(img.width for img in images)
        max_h = max(img.height for img in images)

        if request.max_cell_width and max_w > request.max_cell_width:
            scale = request.max_cell_width / max_w
            max_w = request.max_cell_width
            max_h = int(max_h * scale)
            # Scale all images proportionally
            scaled_images = []
            for img in images:
                new_w = int(img.width * scale)
                new_h = int(img.height * scale)
                scaled_images.append(img.resize((new_w, new_h), Image.Resampling.LANCZOS))
            images = scaled_images

        # Add space for labels if provided
        label_height = 25 if request.labels else 0

        # Calculate canvas size
        cell_w = max_w + request.spacing
        cell_h = max_h + request.spacing + label_height
        canvas_w = cols * cell_w + request.spacing
        canvas_h = rows * cell_h + request.spacing

        # Parse background color
        bg_color = request.background_color.lstrip('#')
        bg_rgb = tuple(int(bg_color[i:i+2], 16) for i in (0, 2, 4))

        # Create canvas
        canvas = Image.new('RGB', (canvas_w, canvas_h), bg_rgb)

        # Try to load a font for labels
        font = None
        if request.labels:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            except:
                font = ImageFont.load_default()

        # Place images
        draw = ImageDraw.Draw(canvas) if request.labels else None
        for i, img in enumerate(images):
            row = i // cols
            col = i % cols

            # Calculate position (center in cell)
            x = col * cell_w + request.spacing + (max_w - img.width) // 2
            y = row * cell_h + request.spacing

            if request.label_position == "top" and request.labels:
                y += label_height

            # Paste image (handle transparency)
            if img.mode == 'RGBA':
                canvas.paste(img, (x, y), img)
            else:
                canvas.paste(img, (x, y))

            # Add label
            if request.labels and i < len(request.labels) and draw:
                label = request.labels[i]
                label_x = col * cell_w + request.spacing + max_w // 2
                if request.label_position == "bottom":
                    label_y = y + img.height + 5
                else:
                    label_y = row * cell_h + request.spacing + 5

                # Center text
                bbox = draw.textbbox((0, 0), label, font=font)
                text_w = bbox[2] - bbox[0]
                draw.text((label_x - text_w // 2, label_y), label, fill=(0, 0, 0), font=font)

        # Encode output
        buffer = BytesIO()
        save_format = 'JPEG' if request.output_format.lower() in ['jpg', 'jpeg'] else 'PNG'
        if save_format == 'JPEG':
            canvas = canvas.convert('RGB')
        canvas.save(buffer, format=save_format)

        return MontageResponse(
            image_base64=base64.b64encode(buffer.getvalue()).decode('utf-8'),
            width=canvas_w,
            height=canvas_h,
            grid=f"{cols}x{rows}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Montage creation failed: {str(e)}")
