"""Converts the ATS-safe plain-text rewrite into a downloadable DOCX file."""
from io import BytesIO

from docx import Document

SECTION_HEADERS = {"summary", "experience", "education", "skills"}


def build_docx(resume_text: str) -> bytes:
    document = Document()
    for line in resume_text.splitlines():
        stripped = line.strip()
        if not stripped:
            document.add_paragraph("")
            continue
        if stripped.rstrip(":").lower() in SECTION_HEADERS:
            document.add_heading(stripped.rstrip(":"), level=2)
        elif stripped.startswith("- "):
            document.add_paragraph(stripped[2:], style="List Bullet")
        else:
            document.add_paragraph(stripped)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
