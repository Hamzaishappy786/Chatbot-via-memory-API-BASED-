import base64
from groq import Groq
from app.config import settings
from app.llm.base import LLMProvider


class GroqProvider(LLMProvider):
    def __init__(self):
        self._client = Groq(api_key=settings.groq_api_key)
        self._text_model = settings.groq_text_model
        self._vision_model = settings.groq_vision_model

    def chat(self, messages: list[dict], temperature: float = 0.0) -> str:
        response = self._client.chat.completions.create(
            model=self._text_model,
            messages=messages,
            temperature=temperature,
            max_tokens=2048,
        )
        return response.choices[0].message.content

    def vision(self, prompt: str, image_base64: str, temperature: float = 0.0) -> str:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}",
                        },
                    },
                ],
            }
        ]
        response = self._client.chat.completions.create(
            model=self._vision_model,
            messages=messages,
            temperature=temperature,
            max_tokens=1024,
        )
        return response.choices[0].message.content

    def is_connected(self) -> bool:
        try:
            self._client.models.list()
            return True
        except Exception:
            return False
