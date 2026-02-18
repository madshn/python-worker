# Python Worker

**Location:** `~/ops/python-worker/`
**Role:** Image processing, AI generation, and stock photo search service for n8n and Cloud Associates.
**URL:** https://python-worker-0h8m.onrender.com
**Version:** 2.0.0

---

## Purpose

Backend service for the `image-tools` MCP service package. Provides image processing (Pillow), AI generation (Gemini, DALL-E, GPT-Image-1), and stock photo search (Pexels, Pixabay) via HTTP API. Primary consumers: n8n `image-tools` workflow (`hLrdB9z3GjcZmH1K`), Cloud Associates.

---

## Available Capabilities

Query `/capabilities` for machine-readable discovery.

### Image Processing (Pillow 11.0)

| Endpoint | Description |
|----------|-------------|
| `POST /image/info` | Get image metadata (dimensions, mode, format) |
| `POST /image/resize` | Resize with aspect ratio preservation |
| `POST /image/crop` | Crop region by coordinates |
| `POST /image/rotate` | Rotate by arbitrary angle |
| `POST /image/flip` | Flip horizontal or vertical |
| `POST /image/convert` | Convert format (PNG, JPEG, WebP, BMP, TIFF, GIF) |
| `POST /image/compress` | Compress/optimize for web (quality, downscale, strip EXIF) |
| `POST /image/watermark` | Add text watermark (position, opacity, color) |
| `POST /image/adjust` | Adjust brightness/contrast/saturation/sharpness |
| `POST /image/thumbnail` | Generate optimized thumbnail |
| `POST /image/montage` | Combine 2-25 images into grid layout |
| `POST /image/grid-overlay` | Add reference grid for AI vision analysis |

### AI Image Generation

| Endpoint | Description |
|----------|-------------|
| `POST /generate/image` | Text-to-image (Gemini, DALL-E 3, GPT-Image-1) |
| `POST /generate/edit` | Edit image with natural language instruction (Gemini) |

### Stock Photo Search

| Endpoint | Description |
|----------|-------------|
| `POST /stock/search` | Search Pexels and/or Pixabay |

### Planned (Phase 2)

| Capability | Packages | Status |
|------------|----------|--------|
| Markdown to PDF | weasyprint | Planned |
| Markdown to DOCX | python-docx, mistune | Planned |

---

## Input Flexibility

All processing endpoints accept **either**:
- `image_base64` — base64-encoded image data
- `image_url` — URL to download image from

When Kiosk is configured (`KIOSK_UPLOAD_URL`), results are auto-uploaded and a URL is returned. Otherwise, base64 fallback.

---

## Environment Variables

| Variable | Required For | Description |
|----------|-------------|-------------|
| `GEMINI_API_KEY` | Generation | Google Gemini API key |
| `OPENAI_API_KEY` | Generation | OpenAI API key (DALL-E 3, GPT-Image-1) |
| `PEXELS_API_KEY` | Stock search | Pexels API key |
| `PIXABAY_API_KEY` | Stock search | Pixabay API key |
| `KIOSK_UPLOAD_URL` | Auto-upload | Kiosk upload endpoint |
| `KIOSK_API_KEY` | Auto-upload | Kiosk auth key |

---

## n8n Integration

The `image-tools` n8n workflow (`hLrdB9z3GjcZmH1K`) is the MCP gateway to this service. Each n8n tool node maps 1:1 to a python-worker endpoint via HTTP Request.

**MCP path:** `https://flow.rightaim.ai/mcp/image-tools`

**Cold starts:** May take 30-60s on Starter tier. For latency-sensitive workflows, ping `/health` first.

---

## Architecture

```
FastAPI app (app/main.py)
├── routers/
│   ├── image.py      # /image/* processing endpoints
│   ├── generate.py   # /generate/* AI generation endpoints
│   └── stock.py      # /stock/* search endpoints
└── tasks/
    ├── grid_overlay.py   # Grid overlay logic
    └── image_utils.py    # Shared: download, upload, convert utilities
```

---

## Local Development

```bash
docker build -t python-worker .
docker run -p 8000:8000 \
  -e GEMINI_API_KEY=... \
  -e OPENAI_API_KEY=... \
  -e PEXELS_API_KEY=... \
  python-worker

curl http://localhost:8000/health
curl http://localhost:8000/capabilities
```

---

## Deployment

| Property | Value |
|----------|-------|
| Platform | Render (Docker web service) |
| Service ID | `srv-d5sir0ngi27c73cbd4sg` |
| Region | Frankfurt (eu-central) |
| Tier | Starter ($7/mo) |
| Auto-deploy | On push to `main` |
| Monitor | UptimeRobot `802236249` |

---

## Related

- **Bob:** `~/ops/bob/` — Factory manager, owns this service
- **Mira:** `~/ops/mira/` — Runtime operator, monitors deployment
- **n8n:** `image-tools` workflow is the MCP gateway
- **Kiosk:** Upload destination for processed/generated images
