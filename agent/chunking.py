from collections.abc import Iterable

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import settings
from .schemas import Block


def sliding_split(text: str, limit: int, overlap: int) -> list[str]:
    """Chia đoạn theo ranh giới tự nhiên và giữ overlap bằng LangChain."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=limit,
        chunk_overlap=min(overlap, limit - 1),
        separators=["\n\n", "\n", ". ", "; ", " ", ""],
        length_function=len,
    )
    return splitter.split_text(text)


def make_chunks(blocks: Iterable[Block]) -> list[dict]:
    """Nhóm nội dung theo cây H1/H2/H3 rồi chia section có overlap."""
    headings = ["", "", ""]
    paragraphs: list[Block] = []
    chunks: list[dict] = []

    def flush() -> None:
        """Đẩy section hiện tại thành chunk kèm breadcrumb và số trang."""
        if not paragraphs:
            return
        title = " > ".join(item for item in headings if item)
        prefix = f"Tiêu đề: {title}\n\n" if title else ""
        body_limit = max(200, settings.chunk_size - len(prefix))
        body = "\n\n".join(item.text for item in paragraphs)
        for part in sliding_split(body, body_limit, min(settings.overlap, body_limit // 3)):
            chunks.append({
                "text": prefix + part,
                "headings": headings.copy(),
                "page": next((item.page for item in paragraphs if item.page), None),
            })
        paragraphs.clear()

    for block in blocks:
        if block.level:
            flush()
            headings[block.level - 1] = block.text
            headings[block.level:] = [""] * (3 - block.level)
        else:
            paragraphs.append(block)
    flush()
    return chunks

