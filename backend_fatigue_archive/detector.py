"""MediaPipe-based fatigue detector."""

from __future__ import annotations

import time
from collections import deque
from pathlib import Path
import os

import cv2
import numpy as np

MPL_CONFIG_DIR = Path(__file__).resolve().parent.parent / ".matplotlib-cache"
MPL_CONFIG_DIR.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))

import mediapipe as mp

from . import config
from .utils import collect_points, eye_aspect_ratio, mouth_open_ratio, resize_frame


LEFT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
RIGHT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
NOSE_INDICES = [1, 2, 98, 327]
LEFT_EAR_INDICES = [234]
RIGHT_EAR_INDICES = [454]

MOUTH_TOP = 13
MOUTH_BOTTOM = 14
MOUTH_LEFT = 78
MOUTH_RIGHT = 308
NOSE_TIP = 1


class FatigueDetector:
    """Stateful detector for one webcam session."""

    def __init__(self) -> None:
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.eye_closed_since: float | None = None
        self.yawn_since: float | None = None
        self.was_eye_closed = False
        self.was_long_eye_closure = False
        self.was_yawning = False
        self.was_head_nodding = False
        self.blink_times: deque[float] = deque()
        self.nose_y_history: deque[tuple[float, float]] = deque()
        self.nose_y_baseline: float | None = None
        self.head_nod_peak_y: float | None = None
        self.last_head_nod_time = 0.0
        self.eye_closure_count = 0
        self.yawn_count = 0
        self.head_nod_count = 0

    def close(self) -> None:
        self.face_mesh.close()

    def process(self, frame: np.ndarray | None) -> dict:
        """Analyze one frame and return a JSON-ready result."""
        if frame is None:
            return self._empty_result()

        frame = resize_frame(frame, config.FRAME_PROCESSING_WIDTH)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)

        if not results.multi_face_landmarks:
            self._reset_continuous_state()
            return self._empty_result()

        now = time.monotonic()
        landmarks = results.multi_face_landmarks[0].landmark

        left_ear = eye_aspect_ratio(landmarks, LEFT_EYE_INDICES)
        right_ear = eye_aspect_ratio(landmarks, RIGHT_EYE_INDICES)
        avg_ear = (left_ear + right_ear) / 2.0
        eyes_closed = avg_ear < config.EYE_ASPECT_RATIO_THRESHOLD

        mouth_ratio = mouth_open_ratio(landmarks, MOUTH_TOP, MOUTH_BOTTOM, MOUTH_LEFT, MOUTH_RIGHT)
        mouth_open = mouth_ratio > config.MOUTH_OPEN_RATIO_THRESHOLD

        closed_too_long = self._track_eye_closure(eyes_closed, now)
        frequent_blinking = self._track_blinks(eyes_closed, now)
        yawning = self._track_yawn(mouth_open, now)
        head_nodding = self._track_head_nod(landmarks[NOSE_TIP].y, now)
        self._track_event_counts(
            closed_too_long=closed_too_long,
            yawning=yawning,
            head_nodding=head_nodding,
        )

        symptoms = []
        if closed_too_long:
            symptoms.append("Eyes closed too long")
        if frequent_blinking:
            symptoms.append("Frequent blinking")
        if yawning:
            symptoms.append("Yawning")
        if head_nodding:
            symptoms.append("Head nodding")

        fatigue_score = self._score_fatigue(
            eyes_closed=eyes_closed,
            closed_too_long=closed_too_long,
            frequent_blinking=frequent_blinking,
            yawning=yawning,
            head_nodding=head_nodding,
        )
        fatigue_level = self._level_from_score(fatigue_score)
        symptom_counts = self._symptom_counts()

        return {
            "faceDetected": True,
            "fatigueLevel": fatigue_level,
            "fatigueScore": fatigue_score,
            "symptoms": symptoms,
            "symptomCounts": symptom_counts,
            "alert": (
                fatigue_score >= config.FATIGUE_ALERT_THRESHOLD
                or self.head_nod_count >= config.HEAD_NOD_COUNT_ALERT_THRESHOLD
            ),
            "landmarks": {
                "leftEye": collect_points(landmarks, LEFT_EYE_INDICES),
                "rightEye": collect_points(landmarks, RIGHT_EYE_INDICES),
                "nose": collect_points(landmarks, NOSE_INDICES),
                "leftEar": collect_points(landmarks, LEFT_EAR_INDICES),
                "rightEar": collect_points(landmarks, RIGHT_EAR_INDICES),
            },
        }

    def clear_session(self) -> None:
        """Clear accumulated symptoms and counters after an acknowledged alert."""
        self.eye_closed_since = None
        self.yawn_since = None
        self.was_eye_closed = False
        self.was_long_eye_closure = False
        self.was_yawning = False
        self.was_head_nodding = False
        self.blink_times.clear()
        self.nose_y_history.clear()
        self.nose_y_baseline = None
        self.head_nod_peak_y = None
        self.last_head_nod_time = 0.0
        self.eye_closure_count = 0
        self.yawn_count = 0
        self.head_nod_count = 0

    def _track_eye_closure(self, eyes_closed: bool, now: float) -> bool:
        if eyes_closed and self.eye_closed_since is None:
            self.eye_closed_since = now
        elif not eyes_closed:
            self.eye_closed_since = None

        return (
            self.eye_closed_since is not None
            and now - self.eye_closed_since >= config.EYE_CLOSED_SECONDS_THRESHOLD
        )

    def _track_blinks(self, eyes_closed: bool, now: float) -> bool:
        if self.was_eye_closed and not eyes_closed:
            self.blink_times.append(now)

        self.was_eye_closed = eyes_closed

        while self.blink_times and now - self.blink_times[0] > config.BLINK_WINDOW_SECONDS:
            self.blink_times.popleft()

        return len(self.blink_times) >= config.BLINK_FREQUENCY_THRESHOLD

    def _track_yawn(self, mouth_open: bool, now: float) -> bool:
        if mouth_open and self.yawn_since is None:
            self.yawn_since = now
        elif not mouth_open:
            self.yawn_since = None

        return self.yawn_since is not None and now - self.yawn_since >= config.YAWN_SECONDS_THRESHOLD

    def _track_head_nod(self, nose_y: float, now: float) -> bool:
        self.nose_y_history.append((now, nose_y))

        while self.nose_y_history and now - self.nose_y_history[0][0] > config.HEAD_NOD_WINDOW_SECONDS:
            self.nose_y_history.popleft()

        if len(self.nose_y_history) < 6:
            return False

        if self.nose_y_baseline is None:
            self.nose_y_baseline = self._average_nose_y()
            return False

        if now - self.last_head_nod_time < config.HEAD_NOD_COOLDOWN_SECONDS:
            self._update_nose_baseline(nose_y)
            return False

        downward_delta = nose_y - self.nose_y_baseline
        if downward_delta >= config.HEAD_NOD_DELTA_THRESHOLD:
            self.head_nod_peak_y = max(self.head_nod_peak_y or nose_y, nose_y)
            return False

        if self.head_nod_peak_y is not None:
            rebound_delta = self.head_nod_peak_y - nose_y
            returned_near_baseline = abs(nose_y - self.nose_y_baseline) <= config.HEAD_NOD_REBOUND_THRESHOLD
            if rebound_delta >= config.HEAD_NOD_REBOUND_THRESHOLD and returned_near_baseline:
                self.head_nod_peak_y = None
                self.last_head_nod_time = now
                self._update_nose_baseline(nose_y)
                return True

        self._update_nose_baseline(nose_y)
        return False

    def _average_nose_y(self) -> float:
        return sum(value for _, value in self.nose_y_history) / len(self.nose_y_history)

    def _update_nose_baseline(self, nose_y: float) -> None:
        if self.head_nod_peak_y is not None:
            return
        if self.nose_y_baseline is None:
            self.nose_y_baseline = nose_y
            return
        self.nose_y_baseline = (self.nose_y_baseline * 0.96) + (nose_y * 0.04)

    def _track_event_counts(self, *, closed_too_long: bool, yawning: bool, head_nodding: bool) -> None:
        if closed_too_long and not self.was_long_eye_closure:
            self.eye_closure_count += 1
        if yawning and not self.was_yawning:
            self.yawn_count += 1
        if head_nodding and not self.was_head_nodding:
            self.head_nod_count += 1

        self.was_long_eye_closure = closed_too_long
        self.was_yawning = yawning
        self.was_head_nodding = head_nodding

    def _symptom_counts(self) -> dict[str, int]:
        return {
            "eyeClosures": self.eye_closure_count,
            "blinks": len(self.blink_times),
            "yawns": self.yawn_count,
            "headNods": self.head_nod_count,
        }

    def _score_fatigue(
        self,
        *,
        eyes_closed: bool,
        closed_too_long: bool,
        frequent_blinking: bool,
        yawning: bool,
        head_nodding: bool,
    ) -> int:
        score = 0
        if eyes_closed:
            score += 18
        if closed_too_long:
            score += 35
        if frequent_blinking:
            score += 25
        if yawning:
            score += 28
        if head_nodding:
            score += 25
        score += min(self.eye_closure_count * config.EYE_CLOSURE_COUNT_WEIGHT, 24)
        if self.yawn_count >= config.YAWN_COUNT_SCORE_THRESHOLD:
            score += min(self.yawn_count * config.YAWN_COUNT_WEIGHT, 30)
        score += min(self.head_nod_count * config.HEAD_NOD_COUNT_WEIGHT, 45)

        return min(score, 100)

    def _level_from_score(self, score: int) -> str:
        if score >= 75:
            return "High Risk"
        if score >= 50:
            return "Warning"
        if score >= 25:
            return "Mild"
        return "Normal"

    def _reset_continuous_state(self) -> None:
        self.eye_closed_since = None
        self.yawn_since = None
        self.was_eye_closed = False
        self.was_long_eye_closure = False
        self.was_yawning = False
        self.was_head_nodding = False
        self.nose_y_baseline = None
        self.head_nod_peak_y = None

    def _empty_result(self) -> dict:
        return {
            "faceDetected": False,
            "fatigueLevel": "Unknown",
            "fatigueScore": 0,
            "symptoms": [],
            "symptomCounts": self._symptom_counts(),
            "alert": False,
            "landmarks": {},
        }
