# Python Worker

General-purpose Python execution service for n8n workflows and operational tasks.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/image/grid-overlay` | POST | Add reference grid to images |
| `/image/resize` | POST | Resize images |

## Local Development

```bash
# Build
docker build -t python-worker .

# Run
docker run -p 8000:8000 python-worker

# Test
curl http://localhost:8000/health
```

## Deployment

Deployed on Render as a Docker web service with auto-deploy from `main` branch.

## Related

- Mira (runtime ops): `~/ops/mira/`
- Grid overlay origin: `~/ops/aston/scripts/grid_overlay.py`
