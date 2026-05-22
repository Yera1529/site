"""Serve static SD (Investigative Department) template files for download."""

import os
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/templates-sd", tags=["templates-sd"])

SD_DIR = Path(__file__).resolve().parent.parent / "templates_sd"


@router.get("/list")
async def list_sd_templates():
    """Return a list of available SD template filenames."""
    if not SD_DIR.exists():
        return []
    files = sorted(
        f.name for f in SD_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in (".docx", ".doc", ".rtf", ".odt", ".txt")
    )
    return files


@router.get("/download/{filename:path}")
async def download_sd_template(filename: str):
    """Download an SD template file by its exact filename."""
    filepath = SD_DIR / filename
    # Security: ensure the file is within SD_DIR
    try:
        filepath.resolve().relative_to(SD_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    # Use RFC 5987 encoding for Cyrillic filenames
    encoded_name = quote(filepath.name)
    return FileResponse(
        path=str(filepath),
        filename=filepath.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"
        },
    )
