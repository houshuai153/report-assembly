"""导出服务：根据报告数据生成 Word / PDF 字节流。"""

from __future__ import annotations

from .docx_export import build_docx
from .pdf_export import build_pdf

MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


def export_report(report: dict, fmt: str) -> tuple[bytes, str]:
    fmt = (fmt or "docx").lower()
    if fmt == "docx":
        return build_docx(report), MIME["docx"]
    if fmt == "pdf":
        return build_pdf(report), MIME["pdf"]
    raise ValueError(f"不支持的导出格式: {fmt}（可选 docx / pdf）")
