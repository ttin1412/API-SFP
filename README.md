# Secure File Processing API

FastAPI service for the Secure File Processing Platform. This repository is
independent from the Worker repository and currently contains the Phase 0 API
foundation only.

The API will own authentication, authorization, file metadata, signed upload
URLs, and scan-job creation. Uploaded file contents will not be proxied or
processed by this service.

## Requirements

- Python 3.9 or newer (Python 3.12 is used by the container)
- Docker (optional)

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp environments/.env.example .env
uvicorn app.main:app --reload --port 8080
```

Check the service at <http://localhost:8080/health>. The expected response is:

```json
{"status": "ok", "service": "api-sfp"}
```

## Quality checks

```bash
pytest
ruff check .
ruff format --check .
```

## Docker

Build from the repository root and run the image:

```bash
docker build -f docker/Dockerfile -t api-sfp:phase0 .
docker run --rm -p 8080:8080 --env-file .env api-sfp:phase0
```

## Configuration

Configuration is read from environment variables. Copy
`environments/.env.example` to `.env` for local development. The checked-in
example contains no credentials; never commit the local `.env` file or service
account keys.

Cloud integrations are intentionally not initialized in Phase 0, so their
configuration values may remain empty while running the health endpoint.

