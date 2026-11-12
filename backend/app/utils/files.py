import hashlib, os, uuid
from fastapi import HTTPException, UploadFile
from ..config import settings

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UPLOAD_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, settings.upload_dir)) if not os.path.isabs(settings.upload_dir) else settings.upload_dir
os.makedirs(UPLOAD_ROOT, exist_ok=True)

PDF_EXT, IMG_EXT = {".pdf"}, {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
MIME_OK = {"application/pdf", "image/png", "image/jpeg", "image/tiff", "application/octet-stream"}

async def save_upload(f: UploadFile, allowed: set) -> tuple:
    """Stores under a server-generated name (never trusts the client filename) and enforces the size limit."""
    ext = os.path.splitext(f.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(allowed))}")
    if f.content_type and f.content_type not in MIME_OK and not f.content_type.startswith(("image/", "application/pdf")):
        raise HTTPException(400, f"Unexpected MIME type {f.content_type}")
    path = os.path.join(UPLOAD_ROOT, uuid.uuid4().hex + ext)
    limit, size, h = settings.max_upload_size_mb * 1024 * 1024, 0, hashlib.sha256()
    with open(path, "wb") as out:
        while chunk := await f.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close(); os.remove(path)
                raise HTTPException(413, f"File exceeds {settings.max_upload_size_mb} MB limit")
            h.update(chunk); out.write(chunk)
    if size == 0:
        os.remove(path); raise HTTPException(400, "Empty file")
    return path, f.filename, h.hexdigest()
