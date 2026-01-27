# Python Worker

**Location:** `~/ops/python-worker/`
**Role:** General-purpose Python execution service for tasks that n8n can't handle natively.

---

## Purpose

This service provides Python capabilities (Pillow, document generation) to n8n workflows and other consumers via HTTP API.

**Current capabilities:**
- Image processing (grid overlay, resize)

**Planned (Phase 2):**
- Document generation (Markdown → PDF/DOCX/PPTX)

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

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check for Render |
| `/image/grid-overlay` | POST | Add 9x9 reference grid to images |
| `/image/resize` | POST | Resize images with aspect ratio options |

---

## Adding New Tasks

1. Create `app/tasks/new_task.py` with processing logic
2. Add router in `app/routers/new_router.py` if needed
3. Include router in `app/main.py`
4. Push to GitHub → auto-deploy

---

## Local Development

```bash
# Build
docker build -t python-worker .

# Run
docker run -p 8000:8000 python-worker

# Test
curl http://localhost:8000/health
```

---

## Deployment

- **Platform:** Render (Docker web service)
- **Tier:** Free (cold starts acceptable for batch/workflow use)
- **Region:** Frankfurt (eu-central)
- **Auto-deploy:** On push to `main`

---

## Related

- **Mira:** `~/ops/mira/` — Runtime operator, monitors this service
- **Aston:** `~/ops/aston/` — Origin of grid_overlay.py script
- **n8n:** Primary consumer via HTTP Request nodes
