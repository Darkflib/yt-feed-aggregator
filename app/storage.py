"""Storage abstraction for export files (local or Google Cloud Storage)."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import Settings

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract storage backend for export files."""

    @abstractmethod
    async def save(self, filename: str, data: bytes) -> str:
        """
        Save file data and return a storage identifier.

        Args:
            filename: Name of the file to save
            data: Binary data to save

        Returns:
            Storage identifier (path or GCS URI)
        """
        pass

    @abstractmethod
    async def get_download_url(self, storage_id: str) -> str:
        """
        Get download URL for a file.

        Args:
            storage_id: Storage identifier from save()

        Returns:
            Full download URL
        """
        pass

    @abstractmethod
    async def delete(self, storage_id: str) -> bool:
        """
        Delete a file from storage.

        Args:
            storage_id: Storage identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, storage_id: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            storage_id: Storage identifier

        Returns:
            True if exists, False otherwise
        """
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_path = Path(settings.export_local_path)
        self.url_base = settings.export_url_base.rstrip("/")

        # Create exports directory if it doesn't exist
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, filename: str, data: bytes) -> str:
        """Save file to local filesystem."""
        file_path = self.base_path / filename

        # Ensure we're not writing outside the exports directory (security)
        if not file_path.resolve().is_relative_to(self.base_path.resolve()):
            raise ValueError(f"Invalid filename: {filename}")

        file_path.write_bytes(data)
        logger.info(f"Saved export to local storage: {file_path}")

        # Return the filename as storage_id
        return filename

    async def get_download_url(self, storage_id: str) -> str:
        """Get download URL for local file."""
        # Returns URL that will be handled by our API endpoint
        return f"{self.url_base}/api/account/export/download/{storage_id}"

    async def delete(self, storage_id: str) -> bool:
        """Delete file from local filesystem."""
        file_path = self.base_path / storage_id

        # Security check
        if not file_path.resolve().is_relative_to(self.base_path.resolve()):
            logger.error(f"Attempted to delete file outside exports directory: {storage_id}")
            return False

        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted export from local storage: {file_path}")
            return True

        return False

    async def exists(self, storage_id: str) -> bool:
        """Check if file exists in local storage."""
        file_path = self.base_path / storage_id

        # Security check
        if not file_path.resolve().is_relative_to(self.base_path.resolve()):
            return False

        return file_path.exists()

    def get_local_path(self, storage_id: str) -> Path:
        """Get local filesystem path for a storage_id."""
        file_path = self.base_path / storage_id

        # Security check
        if not file_path.resolve().is_relative_to(self.base_path.resolve()):
            raise ValueError(f"Invalid storage_id: {storage_id}")

        return file_path


class GCSStorageBackend(StorageBackend):
    """Google Cloud Storage backend."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.bucket_name = settings.gcs_bucket_name
        self.credentials_file = settings.gcs_credentials_file
        self.url_base = settings.export_url_base.rstrip("/")

        if not self.bucket_name:
            raise ValueError("GCS bucket name is required when using GCS storage backend")

        # Lazy import to avoid requiring google-cloud-storage for local-only deployments
        try:
            from google.cloud import storage
        except ImportError:
            raise ImportError(
                "google-cloud-storage is required for GCS backend. "
                "Install with: pip install google-cloud-storage"
            )

        # Initialize GCS client
        if self.credentials_file:
            self.client = storage.Client.from_service_account_json(self.credentials_file)
        else:
            # Use default credentials (from GOOGLE_APPLICATION_CREDENTIALS env var or metadata)
            self.client = storage.Client()

        self.bucket = self.client.bucket(self.bucket_name)

    async def save(self, filename: str, data: bytes) -> str:
        """Save file to Google Cloud Storage."""
        blob = self.bucket.blob(f"exports/{filename}")
        blob.upload_from_string(data, content_type="application/zip")

        logger.info(f"Saved export to GCS: gs://{self.bucket_name}/exports/{filename}")

        # Return GCS URI as storage_id
        return f"gs://{self.bucket_name}/exports/{filename}"

    async def get_download_url(self, storage_id: str) -> str:
        """Get download URL for GCS file."""
        # Parse GCS URI
        if not storage_id.startswith("gs://"):
            raise ValueError(f"Invalid GCS storage_id: {storage_id}")

        # Extract filename from URI
        filename = storage_id.split("/")[-1]

        # Return URL that will be handled by our API endpoint
        # The API endpoint will validate auth and redirect to GCS signed URL
        return f"{self.url_base}/api/account/export/download/{filename}"

    async def delete(self, storage_id: str) -> bool:
        """Delete file from Google Cloud Storage."""
        if not storage_id.startswith("gs://"):
            logger.error(f"Invalid GCS storage_id: {storage_id}")
            return False

        # Extract blob path
        blob_path = storage_id.replace(f"gs://{self.bucket_name}/", "")
        blob = self.bucket.blob(blob_path)

        if blob.exists():
            blob.delete()
            logger.info(f"Deleted export from GCS: {storage_id}")
            return True

        return False

    async def exists(self, storage_id: str) -> bool:
        """Check if file exists in Google Cloud Storage."""
        if not storage_id.startswith("gs://"):
            return False

        blob_path = storage_id.replace(f"gs://{self.bucket_name}/", "")
        blob = self.bucket.blob(blob_path)
        return blob.exists()

    def get_signed_url(self, storage_id: str, expiration_seconds: int = 3600) -> str:
        """
        Generate a signed URL for direct download from GCS.

        Args:
            storage_id: GCS storage identifier
            expiration_seconds: How long the URL should be valid

        Returns:
            Signed URL for direct download
        """
        if not storage_id.startswith("gs://"):
            raise ValueError(f"Invalid GCS storage_id: {storage_id}")

        blob_path = storage_id.replace(f"gs://{self.bucket_name}/", "")
        blob = self.bucket.blob(blob_path)

        return blob.generate_signed_url(
            version="v4",
            expiration=expiration_seconds,
            method="GET",
        )


def get_storage_backend(settings: Settings) -> StorageBackend:
    """
    Factory function to get the appropriate storage backend.

    Args:
        settings: Application settings

    Returns:
        Configured storage backend instance
    """
    if settings.export_storage_backend == "local":
        return LocalStorageBackend(settings)
    elif settings.export_storage_backend == "gcs":
        return GCSStorageBackend(settings)
    else:
        raise ValueError(f"Unknown storage backend: {settings.export_storage_backend}")
