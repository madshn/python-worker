"""
AI image generation endpoints — multi-model support (Gemini, DALL-E, GPT-Image-1).

All generation endpoints upload results to Kiosk and return URLs.
"""

import base64
import os
from io import BytesIO
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.tasks.image_utils import (
    resolve_image_bytes,
    upload_to_kiosk,
    FORMAT_MIMETYPES,
)

router = APIRouter(prefix="/generate", tags=["generate"])

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


# ---------------------------------------------------------------------------
# /generate/image — multi-model text-to-image
# ---------------------------------------------------------------------------

class GenerateImageRequest(BaseModel):
    prompt: str = Field(..., max_length=4000, description="Text description of the image to generate")
    model: str = Field(
        default="gemini",
        pattern="^(gemini|dall-e-3|gpt-image-1)$",
        description="Model to use: gemini, dall-e-3, or gpt-image-1",
    )
    aspect_ratio: str = Field(
        default="1:1",
        pattern="^(1:1|16:9|9:16|4:3|3:4|3:2|2:3)$",
        description="Aspect ratio (support varies by model)",
    )
    size: str = Field(
        default="1024x1024",
        description="Image size (DALL-E: 1024x1024, 1024x1792, 1792x1024)",
    )
    quality: str = Field(
        default="auto",
        pattern="^(auto|low|medium|high|hd|standard)$",
        description="Quality setting (model-specific)",
    )
    style: Optional[str] = Field(
        None,
        pattern="^(vivid|natural)$",
        description="Style (DALL-E 3 only: vivid or natural)",
    )


class GenerateImageResponse(BaseModel):
    url: Optional[str] = Field(None, description="Kiosk URL for generated image")
    image_base64: Optional[str] = Field(None, description="Base64 fallback when Kiosk unavailable")
    model: str
    revised_prompt: Optional[str] = Field(None, description="Model-revised prompt (if available)")
    width: Optional[int] = None
    height: Optional[int] = None


@router.post("/image", response_model=GenerateImageResponse)
async def generate_image(request: GenerateImageRequest) -> GenerateImageResponse:
    """Generate an image from text using Gemini, DALL-E 3, or GPT-Image-1."""
    if request.model == "gemini":
        return await _generate_gemini(request)
    elif request.model == "dall-e-3":
        return await _generate_dalle3(request)
    elif request.model == "gpt-image-1":
        return await _generate_gpt_image(request)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown model: {request.model}")


async def _generate_gemini(req: GenerateImageRequest) -> GenerateImageResponse:
    """Generate via Gemini 2.0 Flash (native image generation)."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [{"parts": [{"text": req.prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            detail = resp.text[:500]
            raise HTTPException(status_code=502, detail=f"Gemini API error: {detail}")

        data = resp.json()

    # Extract image from response
    candidates = data.get("candidates", [])
    if not candidates:
        raise HTTPException(status_code=502, detail="Gemini returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    image_b64 = None
    revised_prompt = None

    for part in parts:
        if "inlineData" in part:
            image_b64 = part["inlineData"]["data"]
        elif "text" in part:
            revised_prompt = part["text"]

    if not image_b64:
        raise HTTPException(status_code=502, detail="Gemini returned no image data")

    image_bytes = base64.b64decode(image_b64)

    # Get dimensions
    from PIL import Image as PILImage
    img = PILImage.open(BytesIO(image_bytes))

    kiosk_url = await upload_to_kiosk(image_bytes, "generated-gemini.png", "image/png")

    return GenerateImageResponse(
        url=kiosk_url,
        image_base64=image_b64 if not kiosk_url else None,
        model="gemini-2.0-flash",
        revised_prompt=revised_prompt,
        width=img.width,
        height=img.height,
    )


async def _generate_dalle3(req: GenerateImageRequest) -> GenerateImageResponse:
    """Generate via OpenAI DALL-E 3."""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    # Map aspect ratio to DALL-E sizes
    size_map = {
        "1:1": "1024x1024",
        "16:9": "1792x1024",
        "9:16": "1024x1792",
        "4:3": "1792x1024",
        "3:4": "1024x1792",
        "3:2": "1792x1024",
        "2:3": "1024x1792",
    }
    size = size_map.get(req.aspect_ratio, req.size)

    quality_map = {"auto": "standard", "high": "hd", "hd": "hd"}
    quality = quality_map.get(req.quality, "standard")

    payload = {
        "model": "dall-e-3",
        "prompt": req.prompt,
        "n": 1,
        "size": size,
        "quality": quality,
        "response_format": "b64_json",
    }
    if req.style:
        payload["style"] = req.style

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/images/generations",
            json=payload,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        )
        if resp.status_code != 200:
            detail = resp.text[:500]
            raise HTTPException(status_code=502, detail=f"DALL-E API error: {detail}")

        data = resp.json()

    image_data = data["data"][0]
    image_b64 = image_data["b64_json"]
    revised_prompt = image_data.get("revised_prompt")

    image_bytes = base64.b64decode(image_b64)
    from PIL import Image as PILImage
    img = PILImage.open(BytesIO(image_bytes))

    kiosk_url = await upload_to_kiosk(image_bytes, "generated-dalle3.png", "image/png")

    return GenerateImageResponse(
        url=kiosk_url,
        image_base64=image_b64 if not kiosk_url else None,
        model="dall-e-3",
        revised_prompt=revised_prompt,
        width=img.width,
        height=img.height,
    )


async def _generate_gpt_image(req: GenerateImageRequest) -> GenerateImageResponse:
    """Generate via OpenAI GPT-Image-1 (gpt-image-1)."""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    size_map = {
        "1:1": "1024x1024",
        "16:9": "1536x1024",
        "9:16": "1024x1536",
        "4:3": "1536x1024",
        "3:4": "1024x1536",
        "3:2": "1536x1024",
        "2:3": "1024x1536",
    }
    size = size_map.get(req.aspect_ratio, "1024x1024")

    quality_map = {"auto": "auto", "low": "low", "medium": "medium", "high": "high"}
    quality = quality_map.get(req.quality, "auto")

    payload = {
        "model": "gpt-image-1",
        "prompt": req.prompt,
        "n": 1,
        "size": size,
        "quality": quality,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/images/generations",
            json=payload,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        )
        if resp.status_code != 200:
            detail = resp.text[:500]
            raise HTTPException(status_code=502, detail=f"GPT-Image API error: {detail}")

        data = resp.json()

    image_data = data["data"][0]
    image_b64 = image_data.get("b64_json")

    if not image_b64 and image_data.get("url"):
        # Download from URL if b64 not returned
        async with httpx.AsyncClient(timeout=60.0) as client:
            dl = await client.get(image_data["url"])
            image_bytes = dl.content
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    else:
        image_bytes = base64.b64decode(image_b64)

    from PIL import Image as PILImage
    img = PILImage.open(BytesIO(image_bytes))

    kiosk_url = await upload_to_kiosk(image_bytes, "generated-gpt-image.png", "image/png")

    return GenerateImageResponse(
        url=kiosk_url,
        image_base64=image_b64 if not kiosk_url else None,
        model="gpt-image-1",
        revised_prompt=None,
        width=img.width,
        height=img.height,
    )


# ---------------------------------------------------------------------------
# /generate/edit — image editing via Gemini
# ---------------------------------------------------------------------------

class EditImageRequest(BaseModel):
    image_base64: Optional[str] = Field(None, description="Base64-encoded source image")
    image_url: Optional[str] = Field(None, description="URL to source image")
    instruction: str = Field(..., max_length=4000, description="Edit instruction")


class EditImageResponse(BaseModel):
    url: Optional[str] = None
    image_base64: Optional[str] = None
    model: str = "gemini-2.0-flash"
    width: Optional[int] = None
    height: Optional[int] = None


@router.post("/edit", response_model=EditImageResponse)
async def edit_image(request: EditImageRequest) -> EditImageResponse:
    """Edit an existing image using Gemini (inpainting/instruction-based editing)."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    source_bytes = await resolve_image_bytes(request.image_base64, request.image_url)
    source_b64 = base64.b64encode(source_bytes).decode("utf-8")

    # Detect mime type
    from PIL import Image as PILImage
    source_img = PILImage.open(BytesIO(source_bytes))
    mime = "image/png"
    if source_img.format:
        mime = FORMAT_MIMETYPES.get(source_img.format.lower(), "image/png")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [{
            "parts": [
                {"text": request.instruction},
                {"inlineData": {"mimeType": mime, "data": source_b64}},
            ]
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Gemini edit error: {resp.text[:500]}")

        data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise HTTPException(status_code=502, detail="Gemini returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    image_b64 = None
    for part in parts:
        if "inlineData" in part:
            image_b64 = part["inlineData"]["data"]
            break

    if not image_b64:
        raise HTTPException(status_code=502, detail="Gemini edit returned no image")

    image_bytes = base64.b64decode(image_b64)
    result_img = PILImage.open(BytesIO(image_bytes))

    kiosk_url = await upload_to_kiosk(image_bytes, "edited-gemini.png", "image/png")

    return EditImageResponse(
        url=kiosk_url,
        image_base64=image_b64 if not kiosk_url else None,
        width=result_img.width,
        height=result_img.height,
    )
