"""Q&A API routes."""

import json

from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from app.rag.retriever import retrieve, RetrieveError
from app.rag.generator import generate, generate_stream, GenerationError, _format_sources
from app.rag.embedder import EmbeddingError
from app.rag.cache import get_cached, set_cache

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    top_k: int = 5


@router.post("")
async def chat(request: ChatRequest):
    """Non-streaming Q&A (for API clients)."""
    if not request.question.strip():
        raise HTTPException(400, "Question cannot be empty")

    # Check cache
    cached = get_cached(request.question)
    if cached:
        return cached

    try:
        sources = await retrieve(request.question, top_k=request.top_k)
        result = await generate(request.question, sources)
        set_cache(request.question, result["answer"], result["sources"])
        return result
    except EmbeddingError as e:
        raise HTTPException(500, f"Embedding service error: {e}")
    except RetrieveError as e:
        raise HTTPException(500, f"Retrieval error: {e}")
    except GenerationError as e:
        raise HTTPException(500, f"Generation error: {e}")


@router.post("/html", response_class=HTMLResponse)
async def chat_html(question: str = Form(...), top_k: int = Form(5)):
    """Non-streaming Q&A returning HTML (backup)."""
    if not question.strip():
        return "<div class='qa-item'><div class='answer'>请输入问题</div></div>"

    try:
        cached = get_cached(question)
        if cached:
            return _render_qa_html(question, cached["answer"], cached["sources"])

        sources = await retrieve(question, top_k=top_k)
        result = await generate(question, sources)
        set_cache(question, result["answer"], result["sources"])
        return _render_qa_html(question, result["answer"], result["sources"])
    except (EmbeddingError, RetrieveError, GenerationError) as e:
        return f"<div class='qa-item'><div class='answer' style='color:red'>错误：{e}</div></div>"


@router.post("/stream")
async def chat_stream(question: str = Form(...), top_k: int = Form(5)):
    """Streaming Q&A using Server-Sent Events."""
    if not question.strip():
        return StreamingResponse(
            _single_event("error", "请输入问题"),
            media_type="text/event-stream",
        )

    async def event_stream():
        try:
            # Phase 0: Check cache
            cached = get_cached(question)
            if cached:
                yield f"event: status\ndata: 命中缓存\n\n"
                yield f"event: answer\ndata: {_escape_json(cached['answer'])}\n\n"
                source_html = _build_source_html(cached["sources"])
                yield f"event: sources\ndata: {_escape_json(source_html)}\n\n"
                yield f"event: done\ndata: ok\n\n"
                return

            # Phase 1: Retrieve
            yield f"event: status\ndata: 正在检索知识库...\n\n"
            sources = await retrieve(question, top_k=top_k)

            if not sources:
                yield f"event: answer\ndata: 知识库中暂无相关信息，请先上传一些文档。\n\n"
                yield f"event: done\ndata: ok\n\n"
                return

            # Phase 2: Stream answer
            yield f"event: status\ndata: 找到 {len(sources)} 个相关片段，正在生成回答...\n\n"

            source_html = _build_source_html(_format_sources(sources))
            full_answer = ""

            async for token in generate_stream(question, sources):
                full_answer += token
                yield f"event: token\ndata: {_escape_json(token)}\n\n"

            # Cache the result
            set_cache(question, full_answer, _format_sources(sources))

            # Phase 3: Send sources
            yield f"event: sources\ndata: {_escape_json(source_html)}\n\n"
            yield f"event: done\ndata: ok\n\n"

        except EmbeddingError as e:
            yield f"event: error\ndata: 嵌入服务错误：{e}\n\n"
        except RetrieveError as e:
            yield f"event: error\ndata: 检索错误：{e}\n\n"
        except GenerationError as e:
            yield f"event: error\ndata: 生成错误：{e}\n\n"
        except Exception as e:
            yield f"event: error\ndata: 未知错误：{e}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _single_event(event: str, data: str):
    yield f"event: {event}\ndata: {_escape_json(data)}\n\n"


def _render_qa_html(question: str, answer: str, sources: list[dict]) -> str:
    answer_html = answer.replace("\n", "<br>")
    source_html = _build_source_html(sources)
    return f"""
    <div class='qa-item'>
        <div class='question'>Q: {_escape(question)}</div>
        <div class='answer'>{answer_html}</div>
        {source_html}
    </div>
    """


def _build_source_html(sources: list[dict]) -> str:
    if not sources:
        return ""
    html = "<div class='sources'><strong>参考来源：</strong><ul>"
    for s in sources:
        page = f" (第{s['page_number']}页)" if s.get("page_number") else ""
        html += f"<li>【{s['document_name']}】{page} 相关度:{s['score']}<br><small>{s['text'][:150]}...</small></li>"
    html += "</ul></div>"
    return html


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_json(text: str) -> str:
    return json.dumps(text)
