"""Document parsing service – extracts text from .docx, .pdf, and plain text."""

import io
from typing import Tuple


def parse_docx(content: bytes) -> str:
    """Extract plain text from DOCX file bytes."""
    import docx

    file_obj = io.BytesIO(content)
    doc = docx.Document(file_obj)
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_text:
                full_text.append(" | ".join(row_text))
    return "\n\n".join(full_text)


def parse_pdf(content: bytes) -> str:
    """Extract plain text from PDF file bytes."""
    # Try pypdf first
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(content))
        pages_text = []
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                pages_text.append(extracted.strip())
        return "\n\n".join(pages_text)
    except Exception:
        pass

    # Fallback to PyMuPDF (fitz) if installed
    try:
        import fitz

        doc = fitz.open(stream=content, filetype="pdf")
        pages_text = []
        for page in doc:
            pages_text.append(page.get_text())
        return "\n\n".join(pages_text)
    except Exception as exc:
        raise ValueError(f"Failed to parse PDF: {exc}")


def parse_document(filename: str, content: bytes) -> Tuple[str, str]:
    """Parse document based on filename extension.

    Returns:
        (extracted_text, detected_type)
    """
    lower_name = filename.lower()
    if lower_name.endswith(".docx"):
        return parse_docx(content), "docx"
    elif lower_name.endswith(".pdf"):
        return parse_pdf(content), "pdf"
    elif lower_name.endswith((".txt", ".md", ".json", ".csv")):
        return content.decode("utf-8", errors="replace"), "text"
    else:
        # Default try utf-8 text
        try:
            return content.decode("utf-8"), "text"
        except UnicodeDecodeError:
            raise ValueError(f"Unsupported file format for {filename}")

