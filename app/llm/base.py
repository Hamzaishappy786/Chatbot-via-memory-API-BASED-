from abc import ABC, abstractmethod
from collections.abc import Iterator


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], temperature: float = 0.0) -> str:
        pass

    @abstractmethod
    def stream_chat(self, messages: list[dict], temperature: float = 0.0) -> Iterator[str]:
        """Yield answer text deltas as they are produced."""
        pass

    @abstractmethod
    def vision(self, prompt: str, image_base64: str, temperature: float = 0.0) -> str:
        pass
