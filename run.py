from __future__ import annotations

import os


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    try:
        import uvicorn

        from app.main import app

        print("[full] Starting FastAPI mode")
        uvicorn.run(app, host=host, port=port)
        return
    except Exception as exc:  # fallback for offline/missing deps
        print(f"[fallback] FastAPI mode unavailable: {exc}")

    from app.fallback_server import run_fallback_server

    run_fallback_server(host=host, port=port)


if __name__ == "__main__":
    main()
