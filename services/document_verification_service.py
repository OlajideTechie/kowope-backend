import os
import time
import logging

import cloudinary.uploader
import cloudinary.utils
from rest_framework.exceptions import ValidationError

logger = logging.getLogger("upload")

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
BLOCKED_MIME_TYPES = {
    "text/plain",
    "text/csv",
    "application/vnd.ms-excel",
}

UPLOAD_FOLDERS = {
    "driver": "driver_documents",
    "agent": "agent_documents",
}


class DocumentVerificationService:
    """Centralized service for document validation, upload, and access for both drivers and agents."""

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @staticmethod
    def validate_file(file):
        """Validate a document file for size, extension, and MIME type.

        Returns the file unchanged so it can be used as a serializer field validator.
        """
        if not file:
            raise ValidationError("Document file is required.")

        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"Only {', '.join(sorted(ALLOWED_EXTENSIONS))} files are allowed."
            )

        if hasattr(file, "content_type") and file.content_type in BLOCKED_MIME_TYPES:
            raise ValidationError(
                "Unsupported file type. Allowed types: PDF, JPG, JPEG, PNG."
            )

        if file.size > MAX_FILE_SIZE:
            raise ValidationError("Document file size must not exceed 5 MB.")

        return file

    # ------------------------------------------------------------------
    # Cloudinary Upload
    # ------------------------------------------------------------------
    @staticmethod
    def upload_to_cloudinary(file, *, owner_type, owner_id, document_type=None):
        """Upload a file to Cloudinary under the correct folder.

        Args:
            file: An UploadedFile (from DRF/Django).
            owner_type: "driver" or "agent".
            owner_id: UUID of the owner profile (used to namespace the folder).
            document_type: Optional sub-label (e.g. "nin", "license").

        Returns:
            The Cloudinary upload response dict (contains public_id, secure_url, etc.).
        """
        base_folder = UPLOAD_FOLDERS.get(owner_type)
        if not base_folder:
            raise ValidationError(f"Unknown owner type: {owner_type}")

        folder = f"{base_folder}/{owner_id}"

        public_id_parts = [str(owner_id)]
        if document_type:
            public_id_parts.append(document_type)

        try:
            result = cloudinary.uploader.upload(
                file,
                folder=folder,
                resource_type="auto",
                type="private",
                public_id="_".join(public_id_parts),
                overwrite=True,
                invalidate=True,
            )
        except Exception as exc:
            logger.error(
                "Cloudinary upload failed for %s %s: %s",
                owner_type,
                owner_id,
                exc,
            )
            raise ValidationError("Document upload failed. Please try again.")

        return result

    # ------------------------------------------------------------------
    # Signed URL Generation
    # ------------------------------------------------------------------
    @staticmethod
    def get_signed_url(cloudinary_field, *, expires_in=600):
        """Generate a time-limited signed URL for a private Cloudinary resource.

        Args:
            cloudinary_field: A CloudinaryField value (has .public_id).
            expires_in: Seconds until the URL expires (default 600 / 10 min).

        Returns:
            A signed URL string, or None if the field is empty.
        """
        if not cloudinary_field:
            return None

        url, _ = cloudinary.utils.cloudinary_url(
            cloudinary_field.public_id,
            resource_type="auto",
            type="private",
            sign_url=True,
            expires_at=int(time.time() + expires_in),
        )
        return url

    # ------------------------------------------------------------------
    # High-level helpers for each entity
    # ------------------------------------------------------------------
    @staticmethod
    def create_driver_document(driver_profile, document_type, file):
        """Validate, upload, and create a DriverDocument record.

        Returns the created DriverDocument instance.
        """
        from authentication.models import DriverDocument

        DocumentVerificationService.validate_file(file)

        DocumentVerificationService.upload_to_cloudinary(
            file,
            owner_type="driver",
            owner_id=driver_profile.id,
            document_type=document_type,
        )

        document = DriverDocument.objects.create(
            driver=driver_profile,
            document_type=document_type,
            document_file=file,
        )
        return document

    @staticmethod
    def upload_agent_document(agent_profile, file):
        """Validate and upload a NIN document for an agent.

        Saves the CloudinaryField on the agent profile and returns the upload result.
        """
        DocumentVerificationService.validate_file(file)

        result = DocumentVerificationService.upload_to_cloudinary(
            file,
            owner_type="agent",
            owner_id=agent_profile.id,
            document_type="nin",
        )

        agent_profile.nin_document = file
        agent_profile.save(update_fields=["nin_document"])

        return result
