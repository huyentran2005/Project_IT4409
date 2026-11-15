import json
import os
from pathlib import Path

import httpx

from .config import settings


async def _call_llm(prompt: str) -> str:
    """Gọi model chat đang chọn trong cấu hình."""
    async with httpx.AsyncClient(timeout=60) as http:
        if settings.llm_provider == "gemini":
            key = os.getenv("GEMINI_API_KEY")
            if not key:
                raise RuntimeError("Thiếu GEMINI_API_KEY")
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
            response = await http.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": key},
                json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1}},
            )
        elif settings.llm_provider == "openrouter":
            key = os.getenv("OPENROUTER_API_KEY")
            if not key:
                raise RuntimeError("Thiếu OPENROUTER_API_KEY")
            response = await http.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": os.getenv("OPENROUTER_MODEL", "openrouter/free"),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
            )
        else:
            raise ValueError("LLM_PROVIDER chỉ nhận 'gemini' hoặc 'openrouter'")
        response.raise_for_status()
        data = response.json()
        return (
            data["candidates"][0]["content"]["parts"][0]["text"]
            if settings.llm_provider == "gemini"
            else data["choices"][0]["message"]["content"]
        )


async def analyze_question(
    question: str, history: list[dict] | None = None
) -> list[str]:
    """Dùng LLM tách câu hỏi nhiều ý thành các truy vấn độc lập."""
    history_text = ""
    if history:
        history_text = "\n\nLỊCH SỬ GẦN ĐÂY:\n" + "\n".join(
            f"{item['role']}: {str(item['content'])[-1200:]}" for item in history[-8:]
        )
    prompt = (
        "Phân tích câu hỏi tiếng Việt để phục vụ tìm kiếm tài liệu. "
        "Nếu câu hỏi có nhiều ý hoặc nhiều câu hỏi con, hãy tách thành các truy vấn ngắn, "
        "mỗi truy vấn tập trung vào một ý và vẫn giữ đủ ngữ cảnh cần thiết. "
        "Dùng lịch sử gần đây để làm rõ các câu hỏi tiếp nối ngắn hoặc đại từ. "
        "Nếu chỉ có một ý, trả lại chính câu hỏi đó. Tối đa 5 truy vấn. "
        "Chỉ trả về một mảng JSON các chuỗi, không giải thích.\n\n"
        f"Câu hỏi: {question}{history_text}"
    )
    try:
        raw = await _call_llm(prompt)
        start, end = raw.find("["), raw.rfind("]")
        parsed = json.loads(raw[start : end + 1]) if start >= 0 and end > start else None
        if isinstance(parsed, list):
            questions = [item.strip() for item in parsed if isinstance(item, str) and item.strip()]
            if questions:
                return questions[:5]
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return [question]


def build_prompt(
    question: str,
    contexts: list[dict],
    sub_questions: list[str] | None = None,
    history: list[dict] | None = None,
) -> str:
    """Tạo prompt có đánh số context để LLM trích nguồn."""
    evidence = "\n\n".join(
        f"[{index}] {item['text']}\nNguồn: {item.get('source_name') or Path(item['source']).name}, trang: {item.get('page') or 'N/A'}"
        for index, item in enumerate(contexts, 1)
    )
    breakdown = ""
    if sub_questions and len(sub_questions) > 1:
        breakdown = "Các ý cần trả lời đầy đủ:\n" + "\n".join(
            f"- {item}" for item in sub_questions
        ) + "\n\n"
    conversation = ""
    if history:
        conversation = "LỊCH SỬ CHAT GẦN ĐÂY (chỉ dùng để hiểu mạch hội thoại):\n" + "\n".join(
            f"{item['role']}: {str(item['content'])[-1200:]}" for item in history[-8:]
        ) + "\n\n"
    return (
        "Bạn là trợ lý hỏi đáp tài liệu. Chỉ dùng NGỮ CẢNH dưới đây; nếu thiếu dữ liệu hãy nói rõ. "
        "Lịch sử chỉ giúp hiểu câu hỏi tiếp nối; mọi kết luận phải được hỗ trợ bởi NGỮ CẢNH hiện tại. "
        "Trả lời tiếng Việt ngắn gọn, bỏ câu mở đầu rườm rà. Dùng Markdown chuẩn: tiêu đề, đoạn văn, "
        "danh sách gạch đầu dòng và chữ đậm khi phù hợp; mỗi ý chính nằm trên một dòng. Trích nguồn dạng [1], [2]. "
        "Dùng ký tự mũi tên Unicode (→, ←, ↔), không viết mũi tên bằng LaTeX hoặc ký hiệu $. "
        "Không escape các ký hiệu Markdown và không bọc toàn bộ câu trả lời trong code block.\n\n"
        f"{conversation}CÂU HỎI: {question}\n\n{breakdown}NGỮ CẢNH:\n{evidence}"
    )


async def generate_answer(
    question: str,
    contexts: list[dict],
    sub_questions: list[str] | None = None,
    history: list[dict] | None = None,
) -> str:
    """Gọi Gemini hoặc OpenRouter để sinh câu trả lời từ context."""
    prompt = build_prompt(question, contexts, sub_questions, history)
    return await _call_llm(prompt)
