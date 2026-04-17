# Drawing PDF → Excel Extractor

PDF 도면 파일을 업로드하면 텍스트를 추출해서 `.xlsx` 파일로 내려주는 FastAPI 앱입니다.

## 기능
- PDF 업로드
- 1차: PDF 내장 텍스트 추출(PyMuPDF)
- 2차: 텍스트가 없을 때 OCR(RapidOCR)
- Excel 파일 다운로드

## 한계
- 작은 글씨/흐린 스캔 도면은 OCR 정확도가 낮을 수 있습니다.
- 복잡한 도면 표 구조는 자동 분리 정확도가 떨어질 수 있습니다.

## 로컬 실행
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

브라우저에서 `http://localhost:8000` 접속.

## Docker 배포
```bash
docker build -t drawing-ocr:latest .
docker run --rm -p 8000:8000 drawing-ocr:latest
```

## API
- `GET /` : 업로드 화면
- `POST /extract` : PDF 업로드 후 Excel 응답


## 트러블슈팅
### `ERR_CONNECTION_REFUSED` 발생 시
1. 서버 프로세스가 실제로 실행 중인지 확인
   ```bash
   python run.py
   ```
2. 헬스체크로 서버 상태 확인
   ```bash
   curl http://127.0.0.1:8000/healthz
   ```
   `{"status":"ok"}` 가 나오면 서버는 정상입니다.
3. Docker 사용 시 포트 매핑 확인
   ```bash
   docker run --rm -p 8000:8000 drawing-ocr:latest
   ```
4. WSL/원격 환경이라면 `localhost` 대신 해당 호스트 IP로 접속
5. 회사망 프록시/보안SW가 로컬 포트를 차단하는지 확인


## 원클릭 실행
```bash
make up
```

서버가 뜬 뒤 다른 터미널에서:
```bash
make smoke
```


## Fallback Mode (의존성 설치 실패 시)
- `run.py`는 FastAPI 실행이 불가능하면 자동으로 표준 라이브러리 서버로 전환합니다.
- 이 모드에서도 `/`, `/extract`, `/healthz`는 동작합니다.
- 단, OCR/정밀 추출이 아닌 경량 파서이므로 정확도는 낮습니다.
