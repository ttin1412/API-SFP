"""Google Cloud Tasks adapter for worker delivery."""

from __future__ import annotations

import json
from typing import Callable

from google.api_core.exceptions import AlreadyExists
from google.cloud import tasks_v2

from app.jobs.models import Job


class CloudTasksJobQueue:
    """Deliver jobs to a private worker endpoint using named HTTP tasks."""

    def __init__(
        self,
        *,
        project_id: str,
        location: str,
        queue_name: str,
        worker_endpoint: str,
        service_account_email: str = "",
        oidc_audience: str = "",
        client_factory: Callable[[], tasks_v2.CloudTasksClient] | None = None,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.queue_name = queue_name
        self.worker_endpoint = worker_endpoint
        self.service_account_email = service_account_email
        self.oidc_audience = oidc_audience
        self._client_factory = client_factory or tasks_v2.CloudTasksClient

    def enqueue(self, job: Job) -> None:
        """Create a deterministic task, treating a duplicate as success."""
        self._validate_configuration()
        client = self._client_factory()
        parent = client.queue_path(
            self.project_id,
            self.location,
            self.queue_name,
        )
        http_request: dict[str, object] = {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": self.worker_endpoint,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "job_id": job.id,
                    "file_id": job.file_id,
                    "type": job.type.value,
                },
                separators=(",", ":"),
            ).encode(),
        }
        if self.service_account_email:
            http_request["oidc_token"] = {
                "service_account_email": self.service_account_email,
                "audience": self.oidc_audience or self.worker_endpoint,
            }

        task = {
            "name": f"{parent}/tasks/{job.id}",
            "http_request": http_request,
        }
        try:
            client.create_task(request={"parent": parent, "task": task})
        except AlreadyExists:
            # A named task makes redelivery of the storage event idempotent.
            return

    def _validate_configuration(self) -> None:
        missing = [
            name
            for name, value in (
                ("GCP_PROJECT_ID", self.project_id),
                ("QUEUE_LOCATION", self.location),
                ("QUEUE_NAME", self.queue_name),
                ("WORKER_ENDPOINT", self.worker_endpoint),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Missing Cloud Tasks configuration: {', '.join(missing)}")
