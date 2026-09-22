# LLM 客户端: 走 ANTHROPIC_BASE_URL 的 /v1/messages, 支持 tools (function calling)。
# 默认模型 agnes-3.0-flash。把 Anthropic 的工具协议翻译成"工具调用请求"对象。

import json
import os
from typing import Any

import requests

API_KEY = os.environ.get("AGNES_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://apihub.agnes-ai.com")
MODEL = os.environ.get("ANTHROPIC_MODEL", "agnes-3.0-flash")


class LLMError(RuntimeError):
    pass


def messages_call(
    system: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    max_tokens: int = 1500,
    timeout: int = 120,
) -> dict:
    """调用一次模型, 返回 {stop_reason, content:[block...]}。
    content block 可能是 {'type':'text','text':...} 或
    {'type':'tool_use','id','name','input':{...}}。
    """
    if not API_KEY:
        raise LLMError("AGNES_API_KEY / OPENAI_API_KEY not set")
    url = BASE_URL.rstrip("/") + "/v1/messages"
    body: dict[str, Any] = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    if tools:
        body["tools"] = tools
    r = requests.post(
        url,
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01"},
        json=body,
        timeout=timeout,
    )
    if r.status_code != 200:
        raise LLMError(f"LLM http {r.status_code}: {r.text[:400]}")
    data = r.json()
    return data


def extract_tool_uses(content: list[dict]) -> list[dict]:
    """从 assistant content 里取出 tool_use 块。"""
    out = []
    for block in content:
        if block.get("type") == "tool_use":
            out.append(
                {
                    "id": block.get("id"),
                    "name": block.get("name"),
                    "input": block.get("input", {}),
                }
            )
    return out


def extract_text(content: list[dict]) -> str:
    return "\n".join(
        block.get("text", "") for block in content if block.get("type") == "text"
    ).strip()


def tool_result_blocks(tool_uses: list[dict], results: list[str]) -> list[dict]:
    """把工具结果包装成 user 消息里的 tool_result 块。"""
    blocks = []
    for tu, res in zip(tool_uses, results):
        blocks.append({"type": "tool_result", "tool_use_id": tu["id"], "content": res})
    return blocks


if __name__ == "__main__":
    data = messages_call(
        "You are a helpful assistant.",
        [{"role": "user", "content": "say ping"}],
    )
    print(extract_text(data["content"]), "| stop:", data.get("stop_reason"))
