# Explicit imports ensure all parsers are registered even in cached environments
from app.ingestion.parsers.pdf import PDFParser
from app.ingestion.parsers.image import ImageParser
from app.ingestion.parsers.pptx import PPTXParser
from app.ingestion.parsers.docx import DOCXParser
from app.ingestion.parsers.xlsx import XLSXParser
from app.ingestion.parsers.txt import TXTParser

__all__ = ["PDFParser", "ImageParser", "PPTXParser", "DOCXParser", "XLSXParser", "TXTParser"]
