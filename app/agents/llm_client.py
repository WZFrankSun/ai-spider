import asyncio

from openai import OpenAI

from app.config import get_settings

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    return _client


async def chat(prompt: str) -> str | None:
    settings = get_settings()

    def _call():
        response = get_client().chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    try:
        return await asyncio.to_thread(_call)
    except Exception as e:
        print(e)
        return None
