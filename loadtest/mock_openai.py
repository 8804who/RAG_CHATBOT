"""
부하 테스트용 OpenAI 호환 mock 서버 (/v1/chat/completions, /v1/embeddings).

에이전트 1턴 = 모델 호출 2회를 흉내낸다:
  1) tool 결과가 아직 없으면 search_documents tool_call 반환 (retrieval/Qdrant/DB 경로는 실제로 탄다)
  2) tool 결과를 받으면 고정 답변 반환

실행 (loadtest/에서):
  uv run python mock_openai.py
백엔드 (backend/app에서, 셸 env가 .env보다 우선, Langfuse 비활성):
  OPENAI_BASE_URL=http://localhost:9000/v1 OPENAI_API_KEY=sk-mock LANGFUSE_PUBLIC_KEY= LANGFUSE_SECRET_KEY= \
    uv run uvicorn main:app --port 8000
"""

import asyncio
import json
import os
import random
import re
import time
import uuid

import uvicorn
from fastapi import FastAPI, HTTPException, Request

LATENCY_MS = int(os.getenv("MOCK_LATENCY_MS", "800"))
JITTER_MS = int(os.getenv("MOCK_JITTER_MS", "300"))
EMBED_DIMS = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}
RETRIEVAL_TOOL = "search_documents"

app = FastAPI()


async def _fake_latency(base_ms: int) -> None:
    """
    지터를 더한 가짜 응답 지연

    Parameters:
        base_ms(int): 기준 지연 (밀리초), ±JITTER_MS 범위로 흔든다
    """
    await asyncio.sleep(max(0, base_ms + random.randint(-JITTER_MS, JITTER_MS)) / 1000)


def _search_args(tool: dict, query: str) -> dict:
    """
    search_documents tool_call 인자 생성 (routed 모드면 tool description의 첫 번째 컬렉션 선택)

    Parameters:
        tool(dict): 요청의 search_documents function 정의
        query(str): 이번 턴 사용자 질의

    Returns:
        args(dict): tool_call arguments (`query`, routed면 `collection_name` 포함)
    """
    args = {"query": query}
    if "collection_name" in tool["parameters"].get("properties", {}):
        m = re.search(r"^- ([^:\n]+):", tool.get("description", ""), re.MULTILINE)
        args["collection_name"] = m.group(1).strip() if m else ""
    return args


@app.post("/v1/chat/completions")
async def chat_completions(req: Request) -> dict:
    """
    chat completion 응답 생성 (tool 결과가 없으면 search_documents tool_call, 있으면 `[mock]` 답변)

    Parameters:
        req(Request): OpenAI chat completions 요청

    Returns:
        completion(dict): OpenAI chat.completion 형식 응답 (usage 포함)
    """
    body = await req.json()
    if body.get("stream"):
        raise HTTPException(400, "mock does not support stream=true")
    messages = body["messages"]
    tools = {t["function"]["name"]: t["function"] for t in body.get("tools", [])}
    already_searched = any(m["role"] == "tool" for m in messages)
    user_query = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )

    if not already_searched and RETRIEVAL_TOOL in tools:
        args = _search_args(tools[RETRIEVAL_TOOL], str(user_query))
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"call_{uuid.uuid4().hex[:24]}",
                    "type": "function",
                    "function": {"name": RETRIEVAL_TOOL, "arguments": json.dumps(args)},
                }
            ],
        }
        finish_reason, completion_tokens = "tool_calls", 20
    else:
        message = {
            "role": "assistant",
            "content": "[mock] 검색 결과를 바탕으로 한 답변입니다.",
        }
        finish_reason, completion_tokens = "stop", 150

    await _fake_latency(LATENCY_MS)
    # ponytail: 토큰 수는 chars/4 근사. 정확한 비용 시뮬레이션이 필요하면 tiktoken으로 교체
    prompt_tokens = len(json.dumps(messages, ensure_ascii=False)) // 4
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body["model"],
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
                "logprobs": None,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


@app.post("/v1/embeddings")
async def embeddings(req: Request) -> dict:
    """
    모델 차원에 맞춘 무작위 임베딩 응답 생성

    Parameters:
        req(Request): OpenAI embeddings 요청

    Returns:
        embeddings(dict): OpenAI embedding list 형식 응답 (usage 포함)
    """
    body = await req.json()
    inputs = body["input"] if isinstance(body["input"], list) else [body["input"]]
    dim = EMBED_DIMS.get(body["model"], 1536)
    await _fake_latency(50)
    return {
        "object": "list",
        "model": body["model"],
        "data": [
            {
                "object": "embedding",
                "index": i,
                "embedding": [random.uniform(-1, 1) for _ in range(dim)],
            }
            for i in range(len(inputs))
        ],
        "usage": {"prompt_tokens": 8 * len(inputs), "total_tokens": 8 * len(inputs)},
    }


if __name__ == "__main__":
    uvicorn.run(app, port=int(os.getenv("MOCK_PORT", "9000")), log_level="warning")
