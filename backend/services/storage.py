"""Local file storage abstraction with text extraction. Replace this module to support S3/MinIO."""

import os
import uuid
import pdfplumber
import docx2txt
from pathlib import Path
from config import get_settings


class StorageService:
    def __init__(self):
        settings = get_settings()
        self.base_dir = Path(settings.storage_dir)
        self.uploads_dir = self.base_dir / "uploads"
        self.generated_dir = self.base_dir / "generated"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.generated_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, matter_id: str, filename: str, content: bytes) -> str:
        """Save an uploaded file and return its relative storage path."""
        matter_dir = self.uploads_dir / matter_id
        matter_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid.uuid4().hex}_{filename}"
        file_path = matter_dir / safe_name
        file_path.write_bytes(content)
        return str(file_path.relative_to(self.base_dir))

    def get_full_path(self, relative_path: str) -> str:
        """Resolve a relative storage path to an absolute path."""
        return str(self.base_dir / relative_path)

    def delete_file(self, relative_path: str) -> None:
        """Delete a file from storage."""
        full_path = self.base_dir / relative_path
        if full_path.exists():
            full_path.unlink()

    def extract_text(self, relative_path: str, file_type: str) -> str:
        """Extract text content from an uploaded file."""
        full_path = self.base_dir / relative_path
        try:
            if file_type == "pdf":
                return self._extract_pdf(str(full_path))
            elif file_type in ("docx", "doc"):
                return self._extract_docx(str(full_path))
            elif file_type == "txt":
                return full_path.read_text(encoding="utf-8", errors="ignore")
            elif file_type == "rtf":
                return self._extract_rtf(str(full_path))
            elif file_type == "odt":
                return self._extract_odt(str(full_path))
        except Exception as e:
            return f"[Ошибка извлечения текста: {e}]"
        return ""

    @staticmethod
    def _extract_pdf(path: str) -> str:
        text_parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_docx(path: str) -> str:
        return docx2txt.process(path)

    @staticmethod
    def _extract_rtf(path: str) -> str:
        """Best-effort RTF extraction by stripping RTF control words."""
        import re
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()
        text = re.sub(r"\\[a-z]+\d*\s?", " ", raw)
        text = re.sub(r"[{}]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _extract_odt(path: str) -> str:
        """Extract text from ODT (ZIP of XML) files."""
        import zipfile
        import re
        with zipfile.ZipFile(path, "r") as z:
            if "content.xml" not in z.namelist():
                return ""
            xml = z.read("content.xml").decode("utf-8", errors="ignore")
        text = re.sub(r"<[^>]+>", " ", xml)
        text = re.sub(r"\s+", " ", text).strip()
        return text
