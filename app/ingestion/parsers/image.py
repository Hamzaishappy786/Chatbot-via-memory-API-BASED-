import base64
import io
from PIL import Image
from app.ingestion.parsers.base import BaseParser, ParsedContent


class ImageParser(BaseParser):
    @staticmethod
    def supported_extensions() -> list[str]:
        return [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]

    def parse(self, file_path: str) -> ParsedContent:
        img = Image.open(file_path).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        return ParsedContent(
            text_blocks=[],
            images=[{
                "image_base64": img_b64,
                "page": 1,
                "source": "standalone",
            }],
        )
