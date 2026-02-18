"""
Stock photo search endpoints — Pexels and Pixabay.

Returns structured results with URLs, dimensions, and attribution.
No image downloading — returns source URLs for the consumer to use.
"""

import os
from typing import Optional, List

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/stock", tags=["stock"])

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY", "")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class StockPhoto(BaseModel):
    """A single stock photo result."""
    source: str = Field(description="Source platform (pexels or pixabay)")
    id: str
    description: str
    url_page: str = Field(description="Link to photo page (for attribution)")
    url_small: str = Field(description="Small image URL (~640px)")
    url_medium: str = Field(description="Medium image URL (~1280px)")
    url_large: str = Field(description="Large/original image URL")
    width: int
    height: int
    photographer: str
    photographer_url: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = Field(..., max_length=200, description="Search keywords")
    source: str = Field(
        default="pexels",
        pattern="^(pexels|pixabay|both)$",
        description="Search source: pexels, pixabay, or both",
    )
    orientation: Optional[str] = Field(
        None,
        pattern="^(landscape|portrait|square)$",
        description="Filter by orientation",
    )
    color: Optional[str] = Field(
        None,
        description="Filter by color (named color or hex)",
    )
    category: Optional[str] = Field(
        None,
        description="Category filter (pixabay only: nature, business, people, etc.)",
    )
    per_page: int = Field(default=10, ge=1, le=30, description="Results per source")


class SearchResponse(BaseModel):
    results: List[StockPhoto]
    total_results: int
    sources_queried: List[str]


# ---------------------------------------------------------------------------
# /stock/search
# ---------------------------------------------------------------------------

@router.post("/search", response_model=SearchResponse)
async def search_stock(request: SearchRequest) -> SearchResponse:
    """Search stock photo libraries. Returns URLs, dimensions, and attribution."""
    results: List[StockPhoto] = []
    sources_queried: List[str] = []
    total = 0

    if request.source in ("pexels", "both"):
        if PEXELS_API_KEY:
            pexels_results, pexels_total = await _search_pexels(request)
            results.extend(pexels_results)
            total += pexels_total
            sources_queried.append("pexels")

    if request.source in ("pixabay", "both"):
        if PIXABAY_API_KEY:
            pixabay_results, pixabay_total = await _search_pixabay(request)
            results.extend(pixabay_results)
            total += pixabay_total
            sources_queried.append("pixabay")

    if not sources_queried:
        raise HTTPException(
            status_code=500,
            detail="No stock photo API keys configured (PEXELS_API_KEY / PIXABAY_API_KEY)",
        )

    return SearchResponse(
        results=results,
        total_results=total,
        sources_queried=sources_queried,
    )


async def _search_pexels(req: SearchRequest) -> tuple[List[StockPhoto], int]:
    """Search Pexels API."""
    params = {
        "query": req.query,
        "per_page": req.per_page,
    }
    if req.orientation:
        params["orientation"] = req.orientation
    if req.color:
        params["color"] = req.color

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://api.pexels.com/v1/search",
            params=params,
            headers={"Authorization": PEXELS_API_KEY},
        )
        if resp.status_code != 200:
            return [], 0
        data = resp.json()

    photos = []
    for p in data.get("photos", []):
        src = p.get("src", {})
        photos.append(StockPhoto(
            source="pexels",
            id=str(p["id"]),
            description=p.get("alt", ""),
            url_page=p.get("url", ""),
            url_small=src.get("medium", ""),
            url_medium=src.get("large", ""),
            url_large=src.get("original", ""),
            width=p.get("width", 0),
            height=p.get("height", 0),
            photographer=p.get("photographer", ""),
            photographer_url=p.get("photographer_url"),
        ))

    return photos, data.get("total_results", 0)


async def _search_pixabay(req: SearchRequest) -> tuple[List[StockPhoto], int]:
    """Search Pixabay API."""
    params = {
        "key": PIXABAY_API_KEY,
        "q": req.query,
        "per_page": req.per_page,
        "image_type": "photo",
        "safesearch": "true",
    }
    if req.orientation:
        orientation_map = {"landscape": "horizontal", "portrait": "vertical"}
        params["orientation"] = orientation_map.get(req.orientation, req.orientation)
    if req.color:
        params["colors"] = req.color
    if req.category:
        params["category"] = req.category

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://pixabay.com/api/",
            params=params,
        )
        if resp.status_code != 200:
            return [], 0
        data = resp.json()

    photos = []
    for h in data.get("hits", []):
        photos.append(StockPhoto(
            source="pixabay",
            id=str(h["id"]),
            description=h.get("tags", ""),
            url_page=h.get("pageURL", ""),
            url_small=h.get("webformatURL", ""),
            url_medium=h.get("largeImageURL", ""),
            url_large=h.get("fullHDURL", h.get("largeImageURL", "")),
            width=h.get("imageWidth", 0),
            height=h.get("imageHeight", 0),
            photographer=h.get("user", ""),
            photographer_url=f"https://pixabay.com/users/{h.get('user', '')}-{h.get('user_id', '')}/" if h.get("user") else None,
        ))

    return photos, data.get("totalHits", 0)
