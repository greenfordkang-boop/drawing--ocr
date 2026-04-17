from io import BytesIO

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_index_page_renders_upload_form() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "PDF 도면" in response.text
    assert "multipart/form-data" in response.text


def test_extract_rejects_non_pdf_file() -> None:
    response = client.post(
        "/extract",
        files={"file": ("bad.txt", BytesIO(b"not pdf"), "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "PDF 파일만 업로드 가능합니다."


def test_extract_returns_excel_when_native_text_exists(monkeypatch) -> None:
    monkeypatch.setattr(main, "_extract_text_from_pdf_bytes", lambda _: ["A  B", "C  D"])
    monkeypatch.setattr(main, "_ocr_pdf_bytes", lambda _: [])

    response = client.post(
        "/extract",
        files={"file": ("drawing.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
    )

    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment; filename=\"drawing.xlsx\"" in response.headers[
        "content-disposition"
    ]
    assert len(response.content) > 100


def test_extract_falls_back_to_ocr_when_native_text_missing(monkeypatch) -> None:
    monkeypatch.setattr(main, "_extract_text_from_pdf_bytes", lambda _: [])
    monkeypatch.setattr(main, "_ocr_pdf_bytes", lambda _: ["Tag  Value"])

    response = client.post(
        "/extract",
        files={"file": ("scan.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
    )

    assert response.status_code == 200
    assert "attachment; filename=\"scan.xlsx\"" in response.headers["content-disposition"]
    assert len(response.content) > 100


def test_healthz_endpoint() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
