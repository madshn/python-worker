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

## Dependency Management

Automated dependency updates via [Dependabot](https://docs.github.com/en/code-security/dependabot):

| Ecosystem | File | Schedule | Grouping |
|-----------|------|----------|----------|
| pip | `requirements.txt` | Sundays 4am | Minor+patch grouped |
| docker | `Dockerfile` | Sundays 4am | Individual PRs |

**Workflow:**
1. Dependabot creates PRs for available updates
2. Review changelog and test locally if needed
3. Merge to trigger auto-deploy

Configuration: [`.github/dependabot.yml`](.github/dependabot.yml)

## Related

- Mira (runtime ops): `~/ops/mira/`
- Grid overlay origin: `~/ops/aston/scripts/grid_overlay.py`
