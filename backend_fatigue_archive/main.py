"""FastAPI entrypoint for the fatigue detection system."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .detector import FatigueDetector
from .utils import decode_base64_frame


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Fatigue Detection System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/detect")
async def detect_fatigue(websocket: WebSocket) -> None:
    await websocket.accept()
    detector = FatigueDetector()

    try:
        while True:
            payload = await websocket.receive_json()

            if payload.get("action") == "reset":
                detector.clear_session()
                continue

            frame = decode_base64_frame(payload.get("frame", ""))
            result = detector.process(frame)
            await websocket.send_json(result)
    except WebSocketDisconnect:
        pass
    finally:
        detector.close()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
