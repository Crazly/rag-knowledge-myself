"""Answer generation using DeepSeek-V4 API."""

import json
import logging
from typing import AsyncGenerator

import httpx

from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, LLM_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个个人知识库助手。根据用户提供的参考资料回答用户问题。

规则：
1. 优先基于参考资料回答，如果参考资料不足，可以补充你自己的知识，但要明确说明哪些来自资料、哪些来自你的知识。
2. 回答要准确、简洁，使用中文。
3. 如果参考资料和问题完全无关，直接告诉用户"知识库中没有找到相关信息"。
4. 引用的知识点要标注来源：在引用处使用 [来源:文件名] 标记。"""


class GenerationError(Exception):
    pass


def _build_context(sources: list[dict]) -> str:
    context_parts = []
    for i, s in enumerate(sources, 1):
        context_parts.append(f"[文档{i}] 来源:{s['document_name']}\n{s['text']}")
    return "\n\n".join(context_parts)


async def generate(question: str, sources: list[dict]) -> dict:
    """Generate answer using DeepSeek-V4 with retrieved sources.

    Args:
        question: User's question.
        sources: List of {text, document_name, score, ...}.

    Returns:
        {answer: str, sources: list}.
    """
    if not DEEPSEEK_API_KEY:
        raise GenerationError("DEEPSEEK_API_KEY not set")

    if not sources:
        return {
            "answer": "知识库中暂无相关信息，请先上传一些文档。",
            "sources": [],
        }

    context = _build_context(sources)
    user_message = f"""参考资料：
{context}

用户问题：{question}

请根据参考资料回答。"""

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.7,
                "max_tokens": 2048,
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()

    data = resp.json()
    answer = data["choices"][0]["message"]["content"]

    return {
        "answer": answer,
        "sources": _format_sources(sources),
    }


async def generate_stream(
    question: str, sources: list[dict]
) -> AsyncGenerator[str, None]:
    """Stream answer tokens from DeepSeek-V4."""
    if not DEEPSEEK_API_KEY:
        raise GenerationError("DEEPSEEK_API_KEY not set")

    if not sources:
        yield "知识库中暂无相关信息，请先上传一些文档。"
        return

    context = _build_context(sources)
    user_message = f"""参考资料：
{context}

用户问题：{question}

请根据参考资料回答。"""

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.7,
                "max_tokens": 2048,
                "stream": True,
            },
            timeout=120.0,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


def _format_sources(sources: list[dict]) -> list[dict]:
    citations = []
    for s in sources:
        citations.append({
            "text": s["text"][:300],
            "document_name": s["document_name"],
            "page_number": s.get("page_number"),
            "score": round(s.get("score", 0), 4),
        })
    return citations
