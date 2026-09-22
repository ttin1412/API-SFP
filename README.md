# Secure File Processing API

FastAPI service for the Secure File Processing Platform. This repository is
independent from the Worker repository and currently contains the API through
Phase 5 scan-job creation and queue dispatch.

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

Authentication endpoints are available under `/api/v1/auth`: `register`,
`login`, `refresh`, and `logout`. Access tokens are sent as
`Authorization: Bearer <token>`. Refresh tokens rotate on use and are revoked
by logout. User accounts are persisted in Firestore by default. Set
`GCP_PROJECT_ID`, and use Application Default Credentials locally
(`gcloud auth application-default login`) or a least-privilege service account
in Cloud Run. Set `AUTH_REPOSITORY_BACKEND=memory` only for local ephemeral use.
Refresh-session rotation state is process-local and is not written to Firestore;
users must log in again after an API restart.
The authenticated `GET /api/v1/auth/me` endpoint can be used to validate an
access token. Set `JWT_SECRET_KEY` to a random value of at least 32 characters
outside local development.

`POST /api/v1/files/upload-url` creates `PENDING_UPLOAD` metadata and returns a
short-lived V4 signed URL for a `PUT` directly to
`quarantine/{user_id}/{file_id}` in `GCS_BUCKET_NAME`. The upload request must
send the same `Content-Type` declared when requesting the URL. Configure the
validity window with `SIGNED_UPLOAD_URL_EXPIRE_MINUTES` (15 minutes by default).

Configure an authenticated Eventarc Cloud Storage finalized trigger to send
CloudEvents over its Pub/Sub transport to `POST /api/v1/events/storage`. This
endpoint is the Job Dispatcher: it accepts only events for `GCS_BUCKET_NAME`
and exact quarantine object keys, atomically changes matching metadata from
`PENDING_UPLOAD` to `UPLOADED`, persists a `SECURITY_SCAN` job, and creates an
HTTP task in Cloud Tasks for the Worker.

Both the Firestore job document and Cloud Task use the deterministic ID
`security-scan-{file_id}`. Pub/Sub/Eventarc redelivery therefore cannot create
duplicate logical jobs or tasks. The dispatcher retries task creation even
when the job already exists, which safely repairs an interrupted dispatch.

Configure `QUEUE_NAME`, `QUEUE_LOCATION`, and `WORKER_ENDPOINT`. For a private
Cloud Run Worker, set `WORKER_SERVICE_ACCOUNT_EMAIL` to a service account with
`roles/run.invoker`; `WORKER_OIDC_AUDIENCE` defaults to `WORKER_ENDPOINT` when
left empty. The API service account needs Firestore access and
`roles/cloudtasks.enqueuer`. Protect the dispatcher endpoint with Cloud Run IAM
and grant its invoker role only to the Eventarc delivery service account.

## Quality checks

```bash
pytest
ruff check .
ruff format --check .
```

## Docker

Build from the repository root and run the image:

```bash
docker build -f docker/Dockerfile -t api-sfp:phase1 .
docker run --rm -p 8080:8080 --env-file .env api-sfp:phase1
```

## Configuration

Configuration is read from environment variables. Copy
`environments/.env.example` to `.env` for local development. The checked-in
example contains no credentials; never commit the local `.env` file or service
account keys. For a named Firestore database, set `FIRESTORE_DATABASE` to its
database ID; otherwise retain `(default)`.
