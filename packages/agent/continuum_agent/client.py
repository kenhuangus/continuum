from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-flash"


class QwenClient:
    """OpenAI-compatible client for Qwen Cloud (DashScope)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")
        self.base_url = base_url or DEFAULT_BASE_URL
        self.model = model or os.environ.get("QWEN_MODEL", DEFAULT_MODEL)
        self._client: OpenAI | None = None
        if self.api_key:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @property
    def available(self) -> bool:
        return self._client is not None

    def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> str:
        result = self.chat_with_tools(messages, tools)
        if result.get("type") == "tool_calls":
            return json.dumps(
                [
                    {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}
                    for tc in result["tool_calls"]
                ]
            )
        return result.get("content") or ""

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
    ) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("No API key configured")
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = self._client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        if msg.tool_calls:
            return {
                "type": "tool_calls",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        return {"type": "text", "content": msg.content or ""}

    def chat_json(self, system: str, user: str) -> list[dict[str, Any]]:
        if not self._client:
            raise RuntimeError("No API key configured")
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "[]"
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed.get("memories", parsed.get("items", []))
        return parsed
