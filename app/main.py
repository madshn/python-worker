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
        "version": "1.0.0",
        "status": "ok",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "image": {
                "grid-overlay": "POST /image/grid-overlay",
                "resize": "POST /image/resize",
            },
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint for Render."""
    return {"status": "ok"}
