# Python Worker

**Location:** `~/ops/python-worker/`
**Role:** General-purpose Python execution service for tasks that n8n can't handle natively.
**URL:** https://python-worker-0h8m.onrender.com

---

## Purpose

This service provides Python capabilities (Pillow, document generation) to n8n workflows via HTTP API. Primary consumer is n8n; agents doing local work should use local tools (ImageMagick, Pillow directly, etc.).

---

## Available Capabilities

Query `/capabilities` for machine-readable discovery.

### Image Processing (Pillow 11.0)

| Endpoint | Description | Use Cases |
|----------|-------------|-----------|
| `POST /image/grid-overlay` | Add reference grid overlay for AI vision | UX screenshot review, spatial coordinate analysis |
| `POST /image/resize` | Resize with aspect ratio preservation | Prepare images for LLM context limits, standardize dimensions |
| `POST /image/montage` | Combine multiple images into grid layout | Character reference sheets, before/after comparisons, multi-image LLM context |

### Planned (Phase 2)

| Capability | Packages | Status |
|------------|----------|--------|
| Markdown → PDF | weasyprint | Planned |
| Markdown → DOCX | python-docx, mistune | Planned |
| Markdown → PPTX | python-pptx | Planned |

---

## Endpoint Details

### POST /image/grid-overlay

Add a chess-style coordinate grid (A-I, 1-9) to images for spatial references in vision LLM analysis.

```json
{
  "image_base64": "...",
  "grid_size": 9,
  "alpha": 0.3,
  "include_prompt": true
}
```

### POST /image/resize

```json
{
  "image_base64": "...",
  "max_dimension": 1024,
  "output_format": "jpeg",
  "quality": 85
}
```

### POST /image/montage

Combine 2-25 images into a grid layout. Auto-calculates grid dimensions if columns not specified.

```json
{
  "images": ["base64...", "base64...", "base64..."],
  "columns": 3,
  "spacing": 10,
  "labels": ["Character A", "Character B", "Character C"],
  "max_cell_width": 512
}
```

Response includes `grid` field (e.g., "3x2") for reference.

---

## n8n Integration

Use HTTP Request node:
- **Method:** POST
- **URL:** `https://python-worker-0h8m.onrender.com/image/montage`
- **Body:** JSON with base64-encoded images
- **Headers:** `Content-Type: application/json`

**Note:** Cold starts may take 30-60s on free tier. For latency-sensitive workflows, ping `/health` first.

---

## Requesting New Capabilities

1. **Check `/capabilities`** — May already exist
2. **Create GitHub issue** on `madshn/python-worker`:
   ```
   Capability Request: [name]

   Use case: [what you need]
   Input: [expected format]
   Output: [expected format]
   Packages needed: [if known]
   ```
3. Bob handles implementation, Mira monitors deployment

---

## Architecture

```
FastAPI app (app/main.py)
├── routers/
│   ├── image.py    # /image/* endpoints
│   └── doc.py      # /doc/* endpoints (Phase 2)
└── tasks/
    ├── grid_overlay.py   # Grid overlay logic
    └── doc_convert.py    # Document conversion (Phase 2)
```

---

## Local Development

```bash
# Build
docker build -t python-worker .

# Run
docker run -p 8000:8000 python-worker

# Test
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

- **Mira:** `~/ops/mira/` — Runtime operator, monitors this service
- **Aston:** `~/ops/aston/` — Origin of grid_overlay.py script
- **n8n:** Primary consumer via HTTP Request nodes
