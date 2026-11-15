"""Điều phối phân tích câu hỏi, truy xuất ngữ cảnh và sinh câu trả lời."""

from .llm import analyze_question, generate_answer
from .store import store


async def answer_question(
    question: str,
    top_k: int,
    collection_name: str | None = None,
    history: list[dict] | None = None,
    source_filter: list[str] | None = None,
) -> dict:
    sub_questions = await analyze_question(question, history)
    contexts: list[dict] = []
    seen: set[tuple[str, int | str]] = set()

    for sub_question in sub_questions:
        for item in store.search(
            sub_question, top_k, collection_name=collection_name, source_filter=source_filter
        ):
            identity = (item.get("source", ""), item.get("chunk", item.get("text", "")))
            if identity not in seen:
                contexts.append(item)
                seen.add(identity)

    if not contexts:
        return {
            "answer": "Chưa có dữ liệu phù hợp. Hãy gọi /ingest trước.",
            "sources": [],
            "sub_questions": sub_questions,
        }

    answer = await generate_answer(question, contexts, sub_questions, history)
    return {"answer": answer, "contexts": contexts, "sub_questions": sub_questions}
