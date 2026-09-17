# Secure File Processing Platform

## 1. Project Overview

Build a secure cloud-based file processing platform using Python.

The platform allows authenticated users to upload files directly to cloud object storage. Every uploaded file must be treated as **untrusted input** until it passes a multi-layer security scanning pipeline.

The system uses a microservice-oriented backend architecture with separate API and Worker services.

The API is responsible for authentication, authorization, file metadata, signed URL generation, and job creation.

The Worker is responsible for asynchronous file processing.

The Security Scanner is a component of the Worker and is responsible for evaluating uploaded files through multiple security layers.

The primary engineering goals are:

* Backend engineering
* Microservice architecture
* Asynchronous processing
* Cloud object storage
* Queue-based job processing
* Secure file processing
* File threat detection
* Fault tolerance
* Idempotency
* Security-focused system design

---

# 2. Repository Architecture

Use **separate Git repositories** for the API and Worker.

```text
secure-file-processing-api/
secure-file-processing-worker/
```

Do not put API and Worker in the same repository.

---

# 3. High-Level Architecture

```text
                         ┌─────────────┐
                         │     FE      │
                         └──────┬──────┘
                                │
                                │ REST API
                                ▼
                    ┌─────────────────────┐
                    │    API Service      │
                    │     Repository      │
                    │                     │
                    │ FastAPI             │
                    │ Authentication      │
                    │ Authorization       │
                    │ File Management     │
                    │ Signed URL          │
                    │ Job Management      │
                    └──────┬──────────────┘
                           │
             ┌─────────────┼───────────────┐
             │             │               │
             ▼             ▼               ▼
        Firestore     Cloud Storage      Queue
                      Quarantine            │
                                            │
                                            ▼
                                ┌─────────────────────┐
                                │   Worker Service    │
                                │     Repository      │
                                │                     │
                                │ Job Consumer        │
                                │ Job Handler         │
                                │ Security Scanner    │
                                │ File Processing     │
                                └──────────┬──────────┘
                                           │
                                    ┌──────┴──────┐
                                    │   Scanner   │
                                    │             │
                                    │ Extension  │
                                    │ MIME       │
                                    │ Magic Bytes│
                                    │ Parser     │
                                    │ Size       │
                                    │ Archive    │
                                    │ Hash       │
                                    │ Path       │
                                    │ Isolation  │
                                    └─────────────┘
```

---

# 4. Responsibilities

## API Service

The API service is responsible for:

* Authentication
* Authorization
* User management
* File metadata
* Upload URL generation
* Signed URL generation
* File status retrieval
* Job creation
* Job status retrieval
* API-level validation
* Updating file metadata

The API must NOT process uploaded file contents.

The API must NOT perform malware scanning.

The API must NOT synchronously process uploaded files.

---

## Worker Service

The Worker service is responsible for:

* Consuming jobs from the queue
* Downloading files from quarantine
* Running the Security Scanner
* Processing files after successful scanning
* Updating file/job status
* Moving safe files to trusted storage
* Deleting or rejecting malicious files
* Retry handling
* Idempotent job execution

---

## Security Scanner

The Security Scanner is a component of the Worker.

It must NOT be implemented as an independent microservice in the initial version.

```text
Worker
│
├── Job Consumer
├── Job Handler
│
├── Security Scanner
│   ├── Extension Checker
│   ├── MIME Checker
│   ├── Magic Bytes Checker
│   ├── File Parser
│   ├── Size Checker
│   ├── Archive Analyzer
│   ├── Hash Checker
│   └── Filename / Path Checker
│
└── File Processor
```

The Scanner returns a structured result to the Worker.

Example:

```json
{
  "status": "REJECTED",
  "reason": "INVALID_FILE_SIGNATURE",
  "layer": "MAGIC_BYTES"
}
```

---

# 5. Complete File Lifecycle

The file lifecycle should be:

```text
PENDING_UPLOAD
       │
       ▼
    UPLOADED
       │
       ▼
    SCANNING
       │
       ├───────────────┐
       ▼               ▼
     SAFE           REJECTED
       │
       ▼
   PROCESSING
       │
       ▼
   COMPLETED
```

Unexpected processing errors:

```text
PROCESSING
    │
    ▼
  FAILED
```

Allowed transitions:

```text
PENDING_UPLOAD → UPLOADED

UPLOADED → SCANNING

SCANNING → SAFE
SCANNING → REJECTED

SAFE → PROCESSING

PROCESSING → COMPLETED
PROCESSING → FAILED
```

Do not allow arbitrary state transitions.

---

# 6. Upload Flow

## Step 1 — FE requests upload URL

```http
POST /api/v1/files/upload-url
```

Request:

```json
{
  "filename": "photo.jpeg",
  "content_type": "image/jpeg",
  "size": 1048576
}
```

API must:

1. Authenticate the user.
2. Validate basic metadata.
3. Validate requested file size.
4. Validate supported extension.
5. Generate a unique `file_id`.
6. Generate a secure storage key.
7. Create Firestore metadata.
8. Set status to `PENDING_UPLOAD`.
9. Generate a signed upload URL.
10. Return the signed URL.

---

# 7. Cloud Storage

Files must first be uploaded to a quarantine location.

```text
Cloud Storage
│
├── quarantine/
│   └── {user_id}/{file_id}
│
└── trusted/
    └── {user_id}/{file_id}
```

Clients must never directly upload into:

```text
trusted/
```

The trusted storage area is only accessible to authorized backend/worker services.

---

# 8. Direct File Upload

The FE uploads directly to Cloud Storage using the signed URL.

```text
FE
 │
 │ Signed URL
 ▼
Cloud Storage
 │
 ▼
quarantine/{user_id}/{file_id}
```

The API must not proxy the file.

This prevents large file uploads from unnecessarily consuming API server resources.

---

# 9. Upload Completion and Job Creation

After the object is successfully uploaded to Cloud Storage, the system must detect the upload event.

Preferred flow:

```text
Cloud Storage
      │
      │ Object Finalized Event
      ▼
API / Event Handler
      │
      ├── Verify object
      ├── Update Firestore
      │       PENDING_UPLOAD → UPLOADED
      │
      └── Create Scan Job
              │
              ▼
            Queue
```

The job should contain:

```json
{
  "job_id": "job_123",
  "file_id": "file_123",
  "type": "SECURITY_SCAN"
}
```

Job creation must be idempotent.

Duplicate storage events must not create duplicate active scan jobs.

---

# 10. Security Scanning Pipeline

The Security Scanner must implement the following security layers.

```text
Uploaded File
      │
      ▼
1. Extension Checker
      │
      ▼
2. MIME Type Checker
      │
      ▼
3. Magic Bytes / File Signature
      │
      ▼
4. File Parser
      │
      ▼
5. Size Checker
      │
      ▼
6. Archive Bomb Analyzer
      │
      ▼
7. Hash Checker
      │
      ▼
8. Filename / Path Traversal Checker
      │
      ▼
9. Isolation Workspace
      │
      ▼
10. Malware Scanner
      │
      ▼
   SAFE / REJECTED
```

The exact order may be adjusted when implementation details require it, but all layers must be implemented.

---

# 11. Security Layer 1 — Extension

The platform must maintain an explicit allowlist of supported extensions.

Initial supported formats:

```text
.jpeg
.jpg
.png
.txt
.zip
```

The extension is only the first validation layer.

An extension must never be treated as proof of the actual file type.

Example:

```text
malware.exe → renamed → photo.jpeg
```

must not automatically be accepted.

Unsupported extensions must result in:

```text
REJECTED
reason = UNSUPPORTED_EXTENSION
```

The supported extension list must be configurable.

---

# 12. Security Layer 2 — MIME Type

Check the MIME type associated with the uploaded file.

Example:

```text
photo.jpeg
expected MIME:
image/jpeg
```

Do not blindly trust the client-provided:

```text
Content-Type
```

The scanner should compare client metadata with the actual detected file type.

Example:

```text
Filename: photo.jpeg
Client MIME: image/jpeg
Detected MIME: application/pdf
```

This should be considered suspicious or invalid according to the security policy.

---

# 13. Security Layer 3 — Magic Bytes / File Signature

Inspect the beginning of the file to determine whether the binary signature matches the expected format.

Example:

```text
JPEG
FF D8 FF

PNG
89 50 4E 47 0D 0A 1A 0A

PDF
25 50 44 46
```

For example:

```text
photo.jpeg
extension = .jpeg
declared MIME = image/jpeg
magic bytes = PDF
```

The scanner must reject this mismatch.

Magic bytes provide stronger evidence of file type than the filename extension.

---

# 14. Security Layer 4 — File Parser

Use the appropriate parser for the detected file type to verify that the file has a valid structure.

Examples:

```text
JPEG → JPEG parser
PNG  → PNG parser
PDF  → PDF parser
ZIP  → ZIP parser
```

Example:

```text
photo.jpeg
     │
     ▼
JPEG Parser
     │
     ▼
Cannot parse as JPEG
     │
     ▼
REJECTED
```

The parser check is intended to verify that the file is structurally valid for the claimed format.

Do not simply open the file using an arbitrary application.

Use format-specific parsers/libraries.

Parser failures must be handled safely and must not crash the Worker.

---

# 15. Security Layer 5 — Size Checker

The maximum uploaded file size is:

```text
50 MB
```

The API should reject obviously oversized requests early.

The Worker must also enforce the limit independently.

Do not rely only on client-provided file size.

The actual object size in Cloud Storage must be verified.

Example:

```text
Actual size > 50 MB
       ↓
REJECTED
       ↓
FILE_TOO_LARGE
```

The limit must be configurable through environment configuration.

---

# 16. Security Layer 6 — Archive Bomb / Decompression Bomb

ZIP and other archive formats require additional validation.

Detect:

* Excessive compression ratio
* Excessive uncompressed size
* Excessive number of files
* Excessive archive nesting
* Nested archives
* Path traversal
* Suspicious filenames

Example:

```text
compressed size:
10 MB

uncompressed size:
10 GB

        ↓

Archive Bomb
        ↓
REJECTED
```

Initial configurable limits:

```text
Maximum archive size: 50 MB
Maximum extracted size: 200 MB
Maximum file count: 1,000
Maximum nesting depth: 3
```

These limits must be configurable.

Do not extract archives into an unrestricted filesystem.

---

# 17. Security Layer 7 — Hashing

Calculate a cryptographic hash of the uploaded file.

Use:

```text
SHA-256
```

The hash serves several purposes.

## Duplicate detection

If:

```text
SHA256(file_A) == SHA256(file_B)
```

the files have the same content with extremely high probability.

Use this to detect duplicate files where appropriate.

## Malicious file hash matching

Maintain a malicious hash database/list.

Example:

```text
SHA256(file)
      │
      ▼
Malicious Hash Database
      │
 ┌────┴────┐
 │         │
MATCH    NO MATCH
 │         │
 ▼         ▼
REJECT   Continue
```

A hash match must immediately result in rejection.

Do not treat "hash not found" as proof that a file is safe.

Hashing is one security layer, not the complete security decision.

---

# 18. Security Layer 8 — Filename / Path Traversal

Never use a user-controlled filename directly as a storage path.

Unsafe:

```text
../../etc/passwd
```

or:

```text
../../malicious/file
```

Generate storage keys using server-controlled identifiers:

```text
quarantine/{user_id}/{file_id}
```

The original filename should only be stored as metadata.

When processing archives, validate every extracted path.

Reject paths containing traversal attempts such as:

```text
../
../../
```

Also prevent absolute paths and platform-specific traversal equivalents.

---

# 19. Security Layer 9 — Isolation Workspace

Security scanning and file processing must occur inside an isolated workspace.

The Worker must never process untrusted files directly in the application root directory.

Use a temporary working directory:

```text
/tmp/file-processing/{job_id}/
```

The workspace should:

* Be unique per job.
* Be deleted after processing.
* Run under a non-root user.
* Have limited filesystem permissions.
* Have CPU and memory limits.
* Have controlled network access.
* Never execute uploaded files.
* Prevent access to unrelated files.

The uploaded file must be treated as potentially malicious during processing.

---


# 21. Scan Result

The Security Scanner must return a structured result.

Example SAFE result:

```json
{
  "status": "SAFE",
  "file_id": "file_123",
  "sha256": "...",
  "detected_type": "image/jpeg"
}
```

Example REJECTED result:

```json
{
  "status": "REJECTED",
  "file_id": "file_123",
  "layer": "MALWARE_SCAN",
  "reason": "MALWARE_DETECTED"
}
```

The Worker uses this result to update Firestore.

---

# 22. Safe File Flow

If every required security layer passes:

```text
SCANNING
    │
    ▼
SAFE
    │
    ▼
PROCESSING
    │
    ▼
Move/Copy to Trusted Storage
    │
    ▼
COMPLETED
```

The file must not enter trusted storage before the security pipeline passes.

---

# 23. Rejected File Flow

If any security layer fails:

```text
SCANNING
    │
    ▼
REJECTED
    │
    ├── Record security event
    │
    └── Delete quarantine object
```

For the initial implementation, delete malicious/rejected files from quarantine after recording the necessary metadata.

Do not expose malicious file contents to the user.

---

# 24. Firestore Data Model

## Files

```text
files/{file_id}
```

Fields:

```text
id
owner_id
original_filename
storage_key
detected_mime_type
declared_mime_type
extension
size
sha256
status
rejection_reason
created_at
updated_at
```

## Jobs

```text
jobs/{job_id}
```

Fields:

```text
id
file_id
type
status
retry_count
error
created_at
updated_at
```

## Security Events

```text
security_events/{event_id}
```

Fields:

```text
id
file_id
user_id
event_type
security_layer
reason
scanner
created_at
```

---

# 25. API Endpoints

Implement:

```text
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout

POST   /api/v1/files/upload-url
GET    /api/v1/files
GET    /api/v1/files/{file_id}
DELETE /api/v1/files/{file_id}

GET    /api/v1/jobs/{job_id}

GET    /health
```

The API must enforce ownership.

A normal user must not be able to access another user's files.

---

# 26. API Repository Structure

Use:

```text
API-SFP/
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── dependencies.py
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── files.py
│   │       └── jobs.py
│   │
│   ├── auth/
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── dependencies.py
│   │
│   ├── files/
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   └── service.py
│   │
│   ├── jobs/
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   └── service.py
│   │
│   ├── storage/
│   │   ├── base.py
│   │   └── gcs.py
│   │
│   ├── database/
│   │   └── firestore.py
│   │
│   ├── queue/
│   │   ├── base.py
│   │   └── cloud_tasks.py
│   │
│   ├── config/
│   │   └── settings.py
│   │
│   └── common/
│       ├── enums.py
│       ├── exceptions.py
│       └── logging.py
│
├── tests/
├── docker/
│   └── Dockerfile
├── environments/
│   └── .env.example
├── requirements.txt
├── requirements-dev.txt
├── README.md
└── SPEC.md
```

---

# 27. Worker Repository Structure

Use:

```text
API-SFP-Workers/
│
├── worker/
│   ├── main.py
│   ├── consumer.py
│   │
│   ├── handlers/
│   │   └── scan_handler.py
│   │
│   ├── scanner/
│   │   ├── service.py
│   │   ├── extension_checker.py
│   │   ├── mime_checker.py
│   │   ├── magic_bytes.py
│   │   ├── parser.py
│   │   ├── size_checker.py
│   │   ├── archive_analyzer.py
│   │   ├── hash_checker.py
│   │   ├── path_checker.py
│   │   └── malware_scanner.py
│   │
│   ├── isolation/
│   │   └── workspace.py
│   │
│   ├── storage/
│   │   ├── base.py
│   │   └── gcs.py
│   │
│   ├── database/
│   │   └── firestore.py
│   │
│   ├── jobs/
│   │   ├── models.py
│   │   └── repository.py
│   │
│   ├── config/
│   │   └── settings.py
│   │
│   └── common/
│       ├── enums.py
│       ├── exceptions.py
│       └── logging.py
│
├── tests/
│   ├── unit/
│   │   └── scanner/
│   ├── integration/
│   └── security/
│
├── docker/
│   └── Dockerfile
├── environments/
│   └── .env.example
├── requirements.txt
├── requirements-dev.txt
├── README.md
└── SPEC.md
```

---

# 28. Security Scanner Design

The scanner should expose a high-level interface:

```python
class SecurityScanner:

    async def scan(self, file_context) -> ScanResult:
        ...
```

Internally:

```text
SecurityScanner
│
├── ExtensionChecker
├── MimeChecker
├── MagicBytesChecker
├── FileParser
├── SizeChecker
├── ArchiveAnalyzer
├── HashChecker
└── PathChecker
```

The scanner should stop early when a critical validation fails.

Example:

```text
Extension
    ↓ PASS
MIME
    ↓ PASS
Magic Bytes
    ↓ FAIL
REJECTED
```

There is no reason to continue to expensive malware scanning after a basic file signature mismatch.

---

# 29. Retry and Idempotency

Jobs must be idempotent.

Example:

```text
Same job received twice
        ↓
Worker detects existing processing/completed state
        ↓
Do not duplicate processing
```

Retry temporary failures.

Do not retry permanent security failures:

```text
UNSUPPORTED_EXTENSION
INVALID_MIME
INVALID_MAGIC_BYTES
INVALID_FILE_STRUCTURE
FILE_TOO_LARGE
ARCHIVE_BOMB
MALWARE_DETECTED
HASH_MATCH
PATH_TRAVERSAL
```

Use exponential backoff for retryable failures.

---

# 30. Testing Requirements

Create tests for every security layer.

## Extension

```text
valid .jpeg
valid .png
unsupported .exe
double extension
```

## MIME

```text
correct MIME
incorrect MIME
spoofed MIME
```

## Magic Bytes

```text
valid JPEG signature
invalid JPEG signature
JPEG extension containing PDF
```

## Parser

```text
valid JPEG
corrupted JPEG
invalid JPEG structure
```

## Size

```text
file < 50 MB
file = 50 MB
file > 50 MB
```

## Archive

```text
normal ZIP
oversized extracted content
too many files
nested archives
path traversal
```

## Hash

```text
duplicate file
known malicious hash
unknown hash
```

## Path Traversal

```text
../../etc/passwd
absolute paths
normal filename
malicious archive entry
```

## Isolation

Test that:

* Temporary workspace is created.
* Files are cleaned up.
* Worker runs without root privileges where possible.
* Uploaded files cannot access unrelated filesystem data.

---

# 31. Local Development

Both repositories must be independently runnable.

Use Docker.

API local environment:

```text
API
 ├── Firestore Emulator
 ├── Storage Emulator / Local Storage Adapter
 └── Queue Emulator / Mock
```

Worker local environment:

```text
Worker
 ├── Firestore Emulator
 ├── Storage Emulator / Local Storage Adapter
 └── ClamAV
```

Use Docker Compose where helpful, but keep API and Worker Docker configurations independent because they belong to different repositories.

---

# 32. Configuration

Use environment variables.

Example API:

```text
APP_ENV=local
GCP_PROJECT_ID=
GCS_BUCKET_NAME=

QUARANTINE_PREFIX=quarantine/
TRUSTED_PREFIX=trusted/

MAX_FILE_SIZE=52428800

QUEUE_NAME=
WORKER_ENDPOINT=
```

Example Worker:

```text
APP_ENV=local
GCP_PROJECT_ID=
GCS_BUCKET_NAME=

QUARANTINE_PREFIX=quarantine/
TRUSTED_PREFIX=trusted/

MAX_FILE_SIZE=52428800
MAX_ARCHIVE_EXTRACTED_SIZE=209715200
MAX_ARCHIVE_FILES=1000
MAX_ARCHIVE_NESTING_DEPTH=3

CLAMAV_HOST=
CLAMAV_PORT=
```

Never commit credentials.

---

# 33. Cloud Deployment

Deploy the API and Worker independently.

```text
API Repository
      ↓
Docker
      ↓
Cloud Run API
```

and:

```text
Worker Repository
      ↓
Docker
      ↓
Cloud Run Worker
```

Cloud infrastructure:

```text
Cloud Run
 ├── API
 └── Worker

Firestore
 │
 └── Metadata

Cloud Storage
 ├── quarantine
 └── trusted

Cloud Tasks
 │
 └── Scan Jobs

ClamAV
```

Configure independent service accounts.

Use least-privilege IAM.

---

# 34. CI/CD

Each repository must have its own CI/CD pipeline.

API:

```text
GitHub
   ↓
Cloud Build
   ↓
Tests
   ↓
Lint
   ↓
Docker Build
   ↓
Deploy API
```

Worker:

```text
GitHub
   ↓
Cloud Build
   ↓
Tests
   ↓
Lint
   ↓
Docker Build
   ↓
Deploy Worker
```

---

# 35. Development Phases

## Phase 0 — Repository Setup

Create two repositories:

```text
API-SFP
API-SFP-Workers
```

Set up:

* Python
* Docker
* pytest
* linting
* formatting
* configuration
* README
* `.env.example`

API must expose:

```text
GET /health
```

Worker must start successfully and expose a basic health mechanism appropriate for its deployment model.

Do not implement security scanning yet.

---

# Phase 1 — API Authentication

Implement:

```text
register
login
refresh
logout
```

Add user authentication and authorization.

---

# Phase 2 — File Metadata

Implement:

```text
POST /files/upload-url
GET /files
GET /files/{file_id}
DELETE /files/{file_id}
```

Create Firestore file documents.

---

# Phase 3 — Signed Upload

Implement Cloud Storage signed URL generation.

File status:

```text
PENDING_UPLOAD
```

Files must be uploaded to:

```text
quarantine/
```

---

# Phase 4 — Upload Event

Implement upload event handling.

Flow:

```text
Cloud Storage
      ↓
Upload Event
      ↓
Update Firestore
      ↓
UPLOADED
```

---

# Phase 5 — Queue and Job Creation

Implement:

```text
UPLOADED
   ↓
Create SECURITY_SCAN Job
   ↓
Queue
```

Implement idempotency.

---

# Phase 6 — Worker

Implement:

```text
Queue
  ↓
Worker
  ↓
Scan Handler
```

Update:

```text
UPLOADED
    ↓
SCANNING
```

Initially use a mock Security Scanner.

---

# Phase 7 — Security Scanner

Implement the security layers in this order:

```text
1. Extension
2. MIME Type
3. Magic Bytes
4. File Parser
5. Size Checker
6. Archive Bomb Detection
7. Hashing
8. Filename / Path Traversal
9. Isolation Workspace
10. Malware Scanner
```

Each layer must have independent unit tests.

---

# Phase 8 — Trusted Storage

Implement:

```text
SAFE
 ↓
PROCESSING
 ↓
trusted/
 ↓
COMPLETED
```

Rejected files:

```text
REJECTED
 ↓
Security Event
 ↓
Delete quarantine object
```

---

# Phase 9 — Reliability

Implement:

* Retry
* Exponential backoff
* Idempotency
* Job timeout
* Failure handling

---

# Phase 10 — Security Hardening

Implement:

* Least-privilege IAM
* Non-root Worker
* Resource limits
* Secure temporary workspace
* Signed URL expiration
* Rate limiting
* Authorization checks
* Audit logging

---

# Phase 11 — Cloud Deployment

Deploy API and Worker independently to Cloud Run.

Connect:

```text
Cloud Storage
Firestore
Cloud Tasks
ClamAV
Cloud Run
```

---

# Phase 12 — CI/CD and Observability

Add:

* CI/CD
* Structured logs
* Request ID
* Job ID
* File ID
* Metrics
* Error tracking
* Basic tracing

---

# 36. MVP Definition of Done

The MVP must support the following complete flow:

```text
Authenticated User
       │
       ▼
API
       │
       │ Generate Signed URL
       ▼
FE
       │
       │ Direct Upload
       ▼
Cloud Storage
       │
       │ quarantine/
       ▼
Upload Event
       │
       ▼
Create Scan Job
       │
       ▼
Queue
       │
       ▼
Worker
       │
       ▼
Security Scanner
       │
       ├───────────────┐
       │               │
      SAFE          REJECTED
       │               │
       ▼               ▼
 Trusted Storage     Delete
       │
       ▼
  COMPLETED
```

The FE must be able to query the API and observe the file status.

---

# 37. Important Engineering Constraints

Codex must follow these rules:

1. API and Worker must remain separate repositories.
2. Security Scanner must remain a Worker component.
3. Do not create a separate Scanner microservice initially.
4. API must never process uploaded file contents.
5. Never trust the filename extension alone.
6. Never trust client-provided MIME type alone.
7. Never trust client-provided file size alone.
8. Never place unscanned files into trusted storage.
9. Never use user-controlled filenames as storage paths.
10. Never execute uploaded files.
11. Never run the Worker as root in production.
12. Keep security checks independently testable.
13. Make jobs idempotent.
14. Validate state transitions.
15. Keep security limits configurable.
16. Do not commit secrets.
17. Do not implement unnecessary infrastructure before the core flow works.
18. Do not claim that any single scanner can prove a file is 100% safe.
19. Prefer defense-in-depth security.
20. Complete and test each development phase before moving to the next.

---

# 38. First Codex Task

Do NOT implement the entire platform immediately.

Start with **Phase 0 only**.

For the API repository:

```text
Create:
- FastAPI application
- Project structure
- Configuration
- Dockerfile
- pytest setup
- linting/formatting
- /health endpoint
- .env.example
- README
```

For the Worker repository:

```text
Create:
- Worker application structure
- Configuration
- Dockerfile
- pytest setup
- linting/formatting
- Worker startup mechanism
- health mechanism
- .env.example
- README
```

After completing Phase 0:

1. Run tests.
2. Run linting.
3. Build Docker images.
4. Verify both applications start.
5. Do not proceed to Phase 1 until Phase 0 is complete.
