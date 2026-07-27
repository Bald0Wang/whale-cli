"""LLM client — OpenAI 兼容接口的薄封装。

配置优先级：构造函数参数 > 环境变量（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from openai import OpenAI


class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.model = model or os.getenv("LLM_MODEL", "deepseek-v4-flash")
        self.temperature = temperature

        if not self.api_key:
            raise ValueError("LLM_API_KEY 环境变量未设置")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None,
        *,
        temperature: Optional[float] = None,
    ):
        api_tools = [t.schema for t in tools] if tools else None

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
        }
        if api_tools:
            kwargs["tools"] = api_tools

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message
