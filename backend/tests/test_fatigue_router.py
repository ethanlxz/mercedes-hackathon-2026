from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers import fatigue as fatigue_router


class FakeFatigueDetector:
    def __init__(self) -> None:
        self.frames = []
        self.reset_calls = 0
        self.closed = False

    def process(self, frame):
        self.frames.append(frame)
        return {
            "faceDetected": True,
            "fatigueLevel": "Normal",
            "fatigueScore": 0,
            "symptoms": [],
            "symptomCounts": {
                "eyeClosures": 0,
                "blinks": 0,
                "yawns": 0,
                "headNods": 0,
            },
            "alert": False,
            "landmarks": {},
        }

    def clear_session(self) -> None:
        self.reset_calls += 1

    def close(self) -> None:
        self.closed = True


def test_fatigue_websocket_processes_frames_resets_and_closes(monkeypatch):
    detectors: list[FakeFatigueDetector] = []

    def create_detector() -> FakeFatigueDetector:
        detector = FakeFatigueDetector()
        detectors.append(detector)
        return detector

    monkeypatch.setattr(fatigue_router, "_create_detector", create_detector)
    monkeypatch.setattr(
        fatigue_router,
        "_decode_base64_frame",
        lambda frame_data: f"decoded:{frame_data}",
    )

    client = TestClient(app)

    with client.websocket_connect("/ws/fatigue/detect") as websocket:
        websocket.send_json({"frame": "first-frame"})
        assert websocket.receive_json()["fatigueLevel"] == "Normal"

        websocket.send_json({"action": "reset"})
        websocket.send_json({"frame": "second-frame"})
        assert websocket.receive_json()["faceDetected"] is True

    detector = detectors[0]
    assert detector.frames == ["decoded:first-frame", "decoded:second-frame"]
    assert detector.reset_calls == 1
    assert detector.closed is True
