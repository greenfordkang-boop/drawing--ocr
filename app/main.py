from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Iterable

import fitz  # PyMuPDF
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from openpyxl import Workbook
from rapidocr_onnxruntime import RapidOCR

app = FastAPI(title="Drawing PDF to Excel", version="0.1.0")
ocr_engine: RapidOCR | None = None


def _get_ocr_engine() -> RapidOCR:
    global ocr_engine
    if ocr_engine is None:
        ocr_engine = RapidOCR()
    return ocr_engine


@dataclass
class ParsedRow:
    values: list[str]


def _split_row(line: str) -> ParsedRow:
    # Split by 2+ spaces, tabs, or vertical bars to approximate table columns
    cells = [c.strip() for c in re.split(r"\s{2,}|\t+|\|", line) if c.strip()]
    return ParsedRow(values=cells if cells else [line.strip()])


def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> list[str]:
    lines: list[str] = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        text = page.get_text("text")
        for raw in text.splitlines():
            cleaned = raw.strip()
            if cleaned:
                lines.append(cleaned)
    doc.close()
    return lines


def _ocr_pdf_bytes(pdf_bytes: bytes) -> list[str]:
    lines: list[str] = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        pix = page.get_pixmap(dpi=300, alpha=False)
        result, _ = _get_ocr_engine()(pix.tobytes("png"))
        if not result:
            continue
        for item in result:
            # RapidOCR result format: [box, text, score]
            if len(item) >= 2 and item[1].strip():
                lines.append(item[1].strip())
    doc.close()
    return lines


def _rows_from_lines(lines: Iterable[str]) -> list[ParsedRow]:
    rows: list[ParsedRow] = []
    for line in lines:
        if not line.strip():
            continue
        rows.append(_split_row(line))
    return rows


def _build_workbook(rows: list[ParsedRow]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Extracted"

    if not rows:
        ws.append(["No text extracted"])
    else:
        for row in rows:
            ws.append(row.values)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
    <html>
      <head><title>PDF Drawing OCR</title></head>
      <body style=\"font-family: sans-serif; max-width: 720px; margin: 2rem auto;\">
        <h2>PDF 도면 → Excel 추출</h2>
        <p>주의: 작은 글씨/저화질 스캔본은 오인식이 발생할 수 있습니다.</p>
        <form action=\"/extract\" method=\"post\" enctype=\"multipart/form-data\">
          <input type=\"file\" name=\"file\" accept=\"application/pdf\" required />
          <button type=\"submit\">엑셀 생성</button>
        </form>
      </body>
    </html>
    """


@app.post("/extract")
async def extract(file: UploadFile = File(...)) -> StreamingResponse:
    if file.content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    lines = _extract_text_from_pdf_bytes(pdf_bytes)
    if not lines:
        lines = _ocr_pdf_bytes(pdf_bytes)

    rows = _rows_from_lines(lines)
    xlsx = _build_workbook(rows)

    filename = (file.filename or "drawing.pdf").rsplit(".", 1)[0] + ".xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
