"""
Python Worker Service — Image processing, AI generation, and stock photo search.
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import require_auth
from app.routers import image, generate, stock

app = FastAPI(
    title="Python Worker",
    description="Image processing, AI generation, and stock photo search service.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers — all require Bearer auth
app.include_router(image.router, dependencies=[Depends(require_auth)])
app.include_router(generate.router, dependencies=[Depends(require_auth)])
app.include_router(stock.router, dependencies=[Depends(require_auth)])


@app.get("/")
async def root():
    return {
        "service": "python-worker",
        "version": "2.0.0",
        "status": "ok",
        "docs": "/docs",
        "capabilities": "/capabilities",
    }


@app.get("/capabilities")
async def capabilities():
    """Machine-readable capabilities manifest for agent discovery."""
    return {
        "service": "python-worker",
        "version": "2.0.0",
        "description": "Image processing, AI generation, and stock photo search service.",
        "packages": {
            "pillow": "11.0.0",
            "fastapi": "0.115.0",
            "httpx": "0.27.0",
        },
        "endpoints": {
            "processing": [
                {"path": "/image/info", "method": "POST", "description": "Get image metadata"},
                {"path": "/image/resize", "method": "POST", "description": "Resize with aspect ratio preservation"},
                {"path": "/image/crop", "method": "POST", "description": "Crop region from image"},
                {"path": "/image/rotate", "method": "POST", "description": "Rotate by arbitrary angle"},
                {"path": "/image/flip", "method": "POST", "description": "Flip horizontal or vertical"},
                {"path": "/image/convert", "method": "POST", "description": "Convert format (PNG, JPEG, WebP, etc.)"},
                {"path": "/image/compress", "method": "POST", "description": "Compress/optimize for web"},
                {"path": "/image/watermark", "method": "POST", "description": "Add text watermark"},
                {"path": "/image/adjust", "method": "POST", "description": "Adjust brightness/contrast/saturation/sharpness"},
                {"path": "/image/thumbnail", "method": "POST", "description": "Generate optimized thumbnail"},
                {"path": "/image/montage", "method": "POST", "description": "Combine images into grid layout"},
                {"path": "/image/grid-overlay", "method": "POST", "description": "Add reference grid for AI vision"},
            ],
            "generation": [
                {"path": "/generate/image", "method": "POST", "description": "AI image generation (Gemini, DALL-E 3, GPT-Image-1)"},
                {"path": "/generate/edit", "method": "POST", "description": "AI image editing (Gemini)"},
            ],
            "stock": [
                {"path": "/stock/search", "method": "POST", "description": "Search stock photos (Pexels, Pixabay)"},
            ],
        },
        "auth": "Bearer token via API_KEY env var — all /image, /generate, /stock endpoints",
        "env_vars": {
            "required": ["API_KEY"],
            "required_for_generation": ["GEMINI_API_KEY", "OPENAI_API_KEY"],
            "required_for_stock": ["PEXELS_API_KEY", "PIXABAY_API_KEY"],
            "optional": ["KIOSK_UPLOAD_URL", "KIOSK_API_KEY"],
        },
        "planned": [
            {"capability": "Markdown to PDF", "packages": ["weasyprint"], "status": "Phase 2"},
            {"capability": "Markdown to DOCX", "packages": ["python-docx", "mistune"], "status": "Phase 2"},
        ],
        "request_new_capability": {
            "method": "Create GitHub issue",
            "repo": "madshn/python-worker",
            "template": "Capability Request: [name]\n\nUse case: [what]\nInput: [format]\nOutput: [format]\nPackages needed: [if known]",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
