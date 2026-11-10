"""Document parsing service – extracts text from .docx and .pdf uploads."""

from app.services.parsing.parser import parse_docx, parse_document, parse_pdf

__all__ = ["parse_document", "parse_docx", "parse_pdf"]
