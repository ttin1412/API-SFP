"""Firestore client construction."""

from functools import lru_cache

from google.cloud import firestore


@lru_cache
def get_firestore_client(
    project_id: str = "", database: str = "(default)"
) -> firestore.Client:
    """Create one Firestore client for each project/database pair.

    Google Application Default Credentials are used. Locally, authenticate with
    ``gcloud auth application-default login`` or set
    ``GOOGLE_APPLICATION_CREDENTIALS``. Cloud Run supplies credentials through
    its service account.
    """
    return firestore.Client(project=project_id or None, database=database)
