import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz
from docx import Document

from .schemas import Block


def clean(text: str) -> str:
    """Chuẩn hóa khoảng trắng trong văn bản."""
    return re.sub(r"[ \t]+", " ", text.replace("\xa0", " ")).strip()


def read_docx(path: Path) -> list[Block]:
    """Đọc DOCX và lấy cấp Heading 1/2/3 từ paragraph style."""
    blocks: list[Block] = []
    for paragraph in Document(path).paragraphs:
        text = clean(paragraph.text)
        if text:
            match = re.match(r"Heading\s*([1-3])$", paragraph.style.name, re.I)
            blocks.append(Block(text, int(match.group(1)) if match else 0))
    return blocks


def read_legacy_doc(path: Path) -> list[Block]:
    """Chuyển DOC cũ sang DOCX bằng LibreOffice trước khi đọc."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("File .doc cần LibreOffice và 'soffice' trong PATH")
    with tempfile.TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "docx", "--outdir", temp_dir, str(path)],
            capture_output=True,
            text=True,
            timeout=90,
        )
        converted = Path(temp_dir) / f"{path.stem}.docx"
        if result.returncode or not converted.exists():
            raise RuntimeError(result.stderr or "Không chuyển đổi được file .doc")
        return read_docx(converted)


def read_pdf(path: Path) -> list[Block]:
    """Đọc PDF và suy luận ba cấp heading từ cỡ font lớn hơn body."""
    raw: list[tuple[str, float, int]] = []
    sizes: list[float] = []
    with fitz.open(path) as document:
        for page_no, page in enumerate(document, 1):
            for block in page.get_text("dict")["blocks"]:
                spans = [span for line in block.get("lines", []) for span in line["spans"] if clean(span["text"])]
                text = clean(" ".join(span["text"] for span in spans))
                if text:
                    size = max(float(span["size"]) for span in spans)
                    raw.append((text, size, page_no))
                    sizes.extend(round(float(span["size"]), 1) for span in spans for _ in span["text"])
    if not raw:
        return []
    body_size = max(set(sizes), key=sizes.count)
    heading_sizes = sorted({size for _, size, _ in raw if size > body_size + 0.5}, reverse=True)[:3]
    levels = {size: level for level, size in enumerate(heading_sizes, 1)}
    return [Block(text, levels.get(size, 0) if len(text) <= 220 else 0, page) for text, size, page in raw]


def read_document(path: Path) -> list[Block]:
    """Chọn bộ đọc phù hợp cho PDF, DOCX hoặc DOC."""
    readers = {".pdf": read_pdf, ".docx": read_docx, ".doc": read_legacy_doc}
    try:
        return readers[path.suffix.lower()](path)
    except KeyError as exc:
        raise ValueError(f"Không hỗ trợ định dạng {path.suffix}") from exc

