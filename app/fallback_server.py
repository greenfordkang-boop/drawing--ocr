from __future__ import annotations

import cgi
import io
import re
import zipfile
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


def extract_lines_from_pdf_bytes(pdf_bytes: bytes) -> list[str]:
    # Very lightweight heuristic parser for text-like tokens in raw PDF streams.
    raw = pdf_bytes.decode("latin-1", errors="ignore")
    candidates = re.findall(r"\(([^()]*)\)", raw)
    lines = [c.strip() for c in candidates if c.strip()]
    return lines[:5000]


def split_row(line: str) -> list[str]:
    cells = [c.strip() for c in re.split(r"\s{2,}|\t+|\|", line) if c.strip()]
    return cells if cells else [line.strip()]


def _cell_ref(row: int, col: int) -> str:
    letters = ""
    col_num = col
    while col_num > 0:
        col_num, rem = divmod(col_num - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row}"


def build_xlsx_bytes(lines: list[str]) -> bytes:
    rows = [split_row(line) for line in lines] if lines else [["No text extracted"]]

    sheet_rows: list[str] = []
    for r_idx, row in enumerate(rows, start=1):
        cells_xml: list[str] = []
        for c_idx, value in enumerate(row, start=1):
            ref = _cell_ref(r_idx, c_idx)
            value_xml = escape(value)
            cells_xml.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{value_xml}</t></is></c>'
            )
        sheet_rows.append(f"<row r=\"{r_idx}\">{''.join(cells_xml)}</row>")

    sheet_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
        "<sheetData>"
        + "".join(sheet_rows)
        + "</sheetData></worksheet>"
    )

    workbook_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
        "<sheets><sheet name=\"Extracted\" sheetId=\"1\" r:id=\"rId1\"/></sheets>"
        "</workbook>"
    )

    content_types_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/xl/workbook.xml\" "
        "ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>"
        "<Override PartName=\"/xl/worksheets/sheet1.xml\" "
        "ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>"
        "</Types>"
    )

    rels_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" "
        "Target=\"xl/workbook.xml\"/>"
        "</Relationships>"
    )

    workbook_rels_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" "
        "Target=\"worksheets/sheet1.xml\"/>"
        "</Relationships>"
    )

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    output.seek(0)
    return output.read()


class FallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/healthz":
            body = b'{"status":"ok","mode":"fallback"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path != "/":
            self.send_error(404)
            return

        html = """
        <html><body style="font-family:sans-serif;max-width:720px;margin:2rem auto;">
          <h2>PDF 도면 → Excel 추출 (Fallback Mode)</h2>
          <p>현재 의존성 미설치 상태라 경량 파서로 동작합니다. 정확도가 낮을 수 있습니다.</p>
          <form action="/extract" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept="application/pdf" required />
            <button type="submit">엑셀 생성</button>
          </form>
        </body></html>
        """.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/extract":
            self.send_error(404)
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type")},
        )

        if "file" not in form:
            self.send_error(400, "file field required")
            return

        upload = form["file"]
        filename = upload.filename or "drawing.pdf"
        if not filename.lower().endswith(".pdf"):
            self.send_error(400, "PDF file required")
            return

        data = upload.file.read()
        lines = extract_lines_from_pdf_bytes(data)
        xlsx = build_xlsx_bytes(lines)

        out_name = filename.rsplit(".", 1)[0] + ".xlsx"
        self.send_response(200)
        self.send_header(
            "Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.send_header("Content-Disposition", f'attachment; filename="{out_name}"')
        self.send_header("Content-Length", str(len(xlsx)))
        self.end_headers()
        self.wfile.write(xlsx)


def run_fallback_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), FallbackHandler)
    print(f"[fallback] Serving on http://{host}:{port}")
    server.serve_forever()
