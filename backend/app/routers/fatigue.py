from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter(tags=["fatigue"])


def _create_detector():
    from backend.app.fatigue.detector import FatigueDetector

    return FatigueDetector()


def _decode_base64_frame(frame_data: str):
    from backend.app.fatigue.utils import decode_base64_frame

    return decode_base64_frame(frame_data)


@router.websocket("/ws/fatigue/detect")
async def detect_fatigue(websocket: WebSocket) -> None:
    await websocket.accept()
    detector = _create_detector()

    try:
        while True:
            payload = await websocket.receive_json()

            if payload.get("action") == "reset":
                detector.clear_session()
                continue

            frame = _decode_base64_frame(payload.get("frame", ""))
            result = detector.process(frame)
            await websocket.send_json(result)
    except WebSocketDisconnect:
        pass
    finally:
        detector.close()
