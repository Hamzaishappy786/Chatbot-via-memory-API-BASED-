from app.ingestion.parsers.base import BaseParser, ParsedContent


class TXTParser(BaseParser):
    @staticmethod
    def supported_extensions() -> list[str]:
        return [".txt", ".md", ".csv"]

    def parse(self, file_path: str) -> ParsedContent:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        return ParsedContent(
            text_blocks=[{"text": text, "page": 1}],
            images=[],
        )
