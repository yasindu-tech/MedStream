from __future__ import annotations

import os
from pathlib import PurePosixPath
from urllib.parse import urlparse

import cloudinary
import cloudinary.uploader


CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "medstream/patient-documents")
MAX_DOCUMENT_SIZE_BYTES = int(os.getenv("MAX_DOCUMENT_SIZE_BYTES", str(10 * 1024 * 1024)))


def configure_cloudinary() -> None:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )


def cloudinary_is_configured() -> bool:
    return bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET)


def upload_patient_document(file_bytes: bytes, filename: str, patient_id: str) -> dict:
    if not cloudinary_is_configured():
        raise RuntimeError("Cloudinary is not configured")

    normalized_name = filename.strip()
    name_parts = normalized_name.rsplit(".", 1)
    public_id = name_parts[0] if len(name_parts) == 2 else normalized_name
    extension = name_parts[1].lower() if len(name_parts) == 2 else ""
    resource_type = "raw" if extension == "pdf" else "image"

    return cloudinary.uploader.upload(
        file_bytes,
        folder=f"{CLOUDINARY_FOLDER}/{patient_id}",
        public_id=public_id,
        overwrite=True,
        resource_type=resource_type,
        type="upload",
        access_mode="public",
    )


def extract_public_id_from_url(file_url: str) -> str | None:
    parsed = urlparse(file_url)
    if not parsed.netloc or "res.cloudinary.com" not in parsed.netloc:
        return None

    path_parts = [part for part in PurePosixPath(parsed.path).parts if part and part != "/"]
    if "upload" not in path_parts:
        return None

    upload_idx = path_parts.index("upload")
    remainder = path_parts[upload_idx + 1 :]
    if not remainder:
        return None

    if remainder[0].startswith("v") and remainder[0][1:].isdigit():
        remainder = remainder[1:]

    if not remainder:
        return None

    last = remainder[-1]
    if "." in last:
        remainder[-1] = last.rsplit(".", 1)[0]

    public_id = "/".join(remainder)
    return public_id or None


def delete_patient_document(file_url: str) -> None:
    if not cloudinary_is_configured():
        return

    public_id = extract_public_id_from_url(file_url)
    if not public_id:
        return

    try:
        cloudinary.uploader.destroy(public_id, resource_type="raw")
    except Exception:
        # Fall back to image type since cloudinary resource type can vary by extension.
        cloudinary.uploader.destroy(public_id, resource_type="image")
