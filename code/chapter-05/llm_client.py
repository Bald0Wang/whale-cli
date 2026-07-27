"""第 1 章 · 最小 LLM 客户端。"""
import os

from openai import OpenAI


class LLMClient:
    def __init__(self) -> None:
        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL")
        self.model = os.getenv("LLM_MODEL")

        if not api_key:
            raise RuntimeError("请设置 LLM_API_KEY")
        if not self.model:
            raise RuntimeError("请设置 LLM_MODEL")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
        )
        return response.choices[0].message.model_dump(exclude_none=True)
