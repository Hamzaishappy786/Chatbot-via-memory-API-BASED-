import base64
import io
import fitz
from PIL import Image
from app.ingestion.parsers.base import BaseParser, ParsedContent


class PDFParser(BaseParser):
    @staticmethod
    def supported_extensions() -> list[str]:
        return [".pdf"]

    def parse(self, file_path: str) -> ParsedContent:
        doc = fitz.open(file_path)
        content = ParsedContent()

        for page_num in range(len(doc)):
            page = doc[page_num]

            text = page.get_text("text").strip()
            if text:
                content.text_blocks.append({
                    "text": text,
                    "page": page_num + 1,
                })

            pix = page.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode()

            content.images.append({
                "image_base64": img_b64,
                "page": page_num + 1,
                "source": "page_render",
            })

            for img_info in page.get_images(full=True):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image and base_image["image"]:
                        embedded_b64 = base64.b64encode(base_image["image"]).decode()
                        content.images.append({
                            "image_base64": embedded_b64,
                            "page": page_num + 1,
                            "source": "embedded",
                        })
                except Exception:
                    continue

        doc.close()
        return content
