"""
Image processing endpoints.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

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
