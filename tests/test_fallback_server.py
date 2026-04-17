from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.fallback_server import build_xlsx_bytes, extract_lines_from_pdf_bytes


def test_extract_lines_from_pdf_bytes_parses_parenthesized_tokens() -> None:
    sample = b"BT (PART NO) Tj (ABC-123) Tj ET"
    lines = extract_lines_from_pdf_bytes(sample)

    assert "PART NO" in lines
    assert "ABC-123" in lines


def test_build_xlsx_bytes_generates_zip_package() -> None:
    content = build_xlsx_bytes(["A  B", "C  D"])

    # XLSX is a ZIP container and starts with PK signature
    assert content[:2] == b"PK"
    assert len(content) > 200
