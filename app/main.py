"""
Python Worker Service — General-purpose Python execution for n8n and other services.

Phase 1: Image processing (grid overlay, resize)
Phase 2: Document generation (Markdown → PDF/DOCX/PPTX)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import image

app = FastAPI(
    title="Python Worker",
    description="General-purpose Python execution service for image processing and document generation.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(image.router)


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "python-worker",
        "version": "1.1.0",
        "status": "ok",
        "docs": "/docs",
        "capabilities": "/capabilities",
    }


@app.get("/capabilities")
async def capabilities():
    """
    Machine-readable capabilities manifest for agent discovery.

    Agents can query this endpoint to understand what services are available
    and how to request new capabilities.
    """
    return {
        "service": "python-worker",
        "version": "1.1.0",
        "description": "General-purpose Python execution service for image processing and document generation.",
        "packages": {
            "pillow": "11.0.0",
            "fastapi": "0.115.0",
            "httpx": "0.27.0",
        },
        "endpoints": [
            {
                "path": "/image/grid-overlay",
                "method": "POST",
                "description": "Add a reference grid overlay to an image for AI vision analysis",
                "use_cases": [
                    "UX screenshot review with spatial references",
                    "Vision LLM coordinate-based analysis",
                ],
                "input": "image_base64 (string), grid_size (2-26), alpha (0.1-1.0)",
                "output": "image_base64 with grid overlay",
            },
            {
                "path": "/image/resize",
                "method": "POST",
                "description": "Resize images with aspect ratio preservation",
                "use_cases": [
                    "Prepare images for LLM context limits",
                    "Standardize dimensions for comparison",
                ],
                "input": "image_base64, width/height/max_dimension",
                "output": "image_base64 resized, width, height",
            },
            {
                "path": "/image/montage",
                "method": "POST",
                "description": "Combine multiple images into a grid layout",
                "use_cases": [
                    "Character reference sheets for consistency",
                    "Before/after comparisons",
                    "Multi-image context for vision LLMs",
                ],
                "input": "images (array of base64), columns, spacing, labels",
                "output": "image_base64 combined montage",
            },
        ],
        "planned": [
            {
                "capability": "Markdown to PDF",
                "packages": ["weasyprint"],
                "status": "Phase 2",
            },
            {
                "capability": "Markdown to DOCX",
                "packages": ["python-docx", "mistune"],
                "status": "Phase 2",
            },
            {
                "capability": "Markdown to PPTX",
                "packages": ["python-pptx"],
                "status": "Phase 2",
            },
        ],
        "request_new_capability": {
            "method": "Create GitHub issue",
            "repo": "madshn/python-worker",
            "template": "Capability Request: [name]\n\nUse case: [describe what you need]\nInput: [expected input format]\nOutput: [expected output format]\nPackages needed: [if known]",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint for Render."""
    return {"status": "ok"}
