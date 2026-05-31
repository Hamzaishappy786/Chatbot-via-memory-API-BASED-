from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ParsedContent:
    text_blocks: list[dict] = field(default_factory=list)
    images: list[dict] = field(default_factory=list)


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> ParsedContent:
        pass

    @staticmethod
    def supported_extensions() -> list[str]:
        return []
