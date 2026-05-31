from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], temperature: float = 0.0) -> str:
        pass

    @abstractmethod
    def vision(self, prompt: str, image_base64: str, temperature: float = 0.0) -> str:
        pass
