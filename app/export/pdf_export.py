"""PDF 导出：reportlab（含中文字体）。"""

from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _register_cjk_font() -> str:
    """注册中文字体，返回字体名。失败则退回 Helvetica。"""
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light"
    except Exception:  # noqa: BLE001
        return "Helvetica"


def _make_table(rows: list[list], font: str) -> Table:
    cell_style = ParagraphStyle("cell", fontName=font, fontSize=9, leading=12)
    data = [[Paragraph(str(c), cell_style) for c in row] for row in rows]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def build_pdf(report: dict) -> bytes:
    font = _register_cjk_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("t", parent=styles["Title"], fontName=font, fontSize=20, leading=26)
    h1_style = ParagraphStyle("h1", parent=styles["Heading1"], fontName=font, fontSize=15, leading=20, spaceBefore=12)
    body_style = ParagraphStyle("b", parent=styles["BodyText"], fontName=font, fontSize=10, leading=15)

    meta = report["metadata"]
    story = [
        Paragraph(f"{meta['report_type']} — 报告初稿", title_style),
        Spacer(1, 0.4 * cm),
        Paragraph(f"Study ID: {report['study_id']}　状态: {report['state']}", body_style),
    ]

    story.append(Paragraph("研究信息", h1_style))
    story.append(_make_table([
        ["研究编号", meta["study_id"]],
        ["分析物", meta["analyte"]],
        ["基质", meta["matrix"]],
        ["物种", meta["species"]],
        ["方法平台", meta["method_platform"]],
        ["报告类型", meta["report_type"]],
    ], font))

    story.append(Paragraph("PK 参数（确定性计算）", h1_style))
    pk_rows = [["受试者", "Cmax", "Tmax", "AUC_last", "AUC_inf", "T1/2"]]
    for subj, p in report["pk_by_subject"].items():
        pk_rows.append([
            subj, str(p.get("Cmax")), str(p.get("Tmax")), str(p.get("AUC_last")),
            "" if p.get("AUC_inf") is None else str(p["AUC_inf"]),
            "" if p.get("T1_2") is None else str(p["T1_2"]),
        ])
    story.append(_make_table(pk_rows, font))

    story.append(Paragraph("质控统计（确定性计算）", h1_style))
    qc = report["qc_summary"]
    story.append(_make_table([
        ["指标", "值"],
        ["总样本数", qc.get("total_samples")],
        ["低于 LLOQ (BLQ)", qc.get("below_loq")],
        ["可定量样本", qc.get("measurable")],
        ["分析批次", qc.get("runs")],
        ["受试者数", qc.get("subjects")],
        ["LLOQ (ng/mL)", qc.get("lloq")],
    ], font))

    story.append(Paragraph("叙述章节（AI 受控生成）", h1_style))
    for key, sec in report["sections"].items():
        story.append(Paragraph(sec["title"], h1_style))
        story.append(Paragraph(sec["text"].replace("\n", "<br/>"), body_style))
        story.append(Spacer(1, 0.3 * cm))

    doc.build(story)
    return buf.getvalue()
