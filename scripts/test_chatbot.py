"""Chạy thử chatbot tương tác với một tài liệu trong thư mục docs."""

import asyncio

from agent.qa import answer_question
from agent.service import ingest_path, safe_target


async def main() -> None:
    file_path = input("Đường dẫn file tương đối trong docs (ví dụ: tai-lieu.pdf): ").strip()
    question = input("Câu hỏi: ").strip()
    if not question:
        raise SystemExit("Câu hỏi không được để trống.")

    target = safe_target(file_path)
    result = ingest_path(target)
    print(f"Đã nạp {result['chunks']} chunks từ {result['files']} file.")

    result = await answer_question(question, top_k=6)
    print("\nCác ý dùng để tìm kiếm:")
    for sub_question in result["sub_questions"]:
        print(f"- {sub_question}")
    print("\nTrả lời:\n" + result["answer"])
    print("\nNguồn:")
    for index, item in enumerate(result.get("contexts", []), 1):
        page = item.get("page") or "N/A"
        print(f"[{index}] {item['source']} (trang {page})")


if __name__ == "__main__":
    asyncio.run(main())
