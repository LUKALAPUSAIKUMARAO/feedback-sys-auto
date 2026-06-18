from abc import ABC, abstractmethod
from groq import AsyncGroq
from app.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

log = structlog.get_logger()

GROQ_PRIMARY_MODEL = "llama-3.3-70b-versatile"
GROQ_FAST_MODEL = "llama3-8b-8192"
GEMINI_FALLBACK_MODEL = "gemini-2.0-flash"


class BaseAgent(ABC):
    name: str = "BaseAgent"

    def __init__(self):
        self.groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self._gemini_client = None

    def _get_gemini(self):
        if self._gemini_client is None and settings.GEMINI_API_KEY:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._gemini_client = genai.GenerativeModel(GEMINI_FALLBACK_MODEL)
        return self._gemini_client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _call_groq(
        self,
        system_prompt: str,
        user_message: str,
        model: str = GROQ_PRIMARY_MODEL,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> str:
        kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await self.groq_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    async def _call_with_fallback(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        try:
            return await self._call_groq(system_prompt, user_message, temperature=temperature, max_tokens=max_tokens)
        except Exception as groq_err:
            log.warning(f"{self.name}.groq_failed_fallback_gemini", error=str(groq_err))
            gemini = self._get_gemini()
            if gemini:
                result = await gemini.generate_content_async(
                    f"{system_prompt}\n\nUser: {user_message}"
                )
                return result.text
            raise groq_err

    @abstractmethod
    async def run(self, *args, **kwargs):
        pass
