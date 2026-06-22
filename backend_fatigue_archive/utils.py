"""Utility helpers for frame decoding and landmark math."""

from __future__ import annotations

import base64
from math import hypot
from typing import Iterable

import cv2
import numpy as np


def decode_base64_frame(frame_data: str) -> np.ndarray | None:
    """Decode a base64 or data-URL image into an OpenCV BGR frame."""
    if not frame_data:
        return None

    if "," in frame_data:
        frame_data = frame_data.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(frame_data, validate=False)
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        return cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    except Exception:
        return None


def resize_frame(frame: np.ndarray, target_width: int) -> np.ndarray:
    """Resize a frame while preserving aspect ratio."""
    height, width = frame.shape[:2]
    if width <= target_width:
        return frame

    scale = target_width / width
    return cv2.resize(frame, (target_width, int(height * scale)))


def landmark_to_point(landmark) -> dict[str, float]:
    """Convert a MediaPipe landmark into a normalized JSON-friendly point."""
    return {"x": float(landmark.x), "y": float(landmark.y)}


def collect_points(landmarks, indices: Iterable[int]) -> list[dict[str, float]]:
    """Return normalized points for selected landmark indices."""
    return [landmark_to_point(landmarks[index]) for index in indices]


def point_distance(a, b) -> float:
    """Calculate distance between two normalized MediaPipe landmarks."""
    return hypot(a.x - b.x, a.y - b.y)


def eye_aspect_ratio(landmarks, eye_indices: list[int]) -> float:
    """Calculate eye aspect ratio from six eye landmarks."""
    p0, p1, p2, p3, p4, p5 = [landmarks[index] for index in eye_indices]
    vertical_a = point_distance(p1, p5)
    vertical_b = point_distance(p2, p4)
    horizontal = point_distance(p0, p3)

    if horizontal == 0:
        return 0.0

    return (vertical_a + vertical_b) / (2.0 * horizontal)


def mouth_open_ratio(landmarks, top_index: int, bottom_index: int, left_index: int, right_index: int) -> float:
    """Calculate mouth opening ratio using vertical and horizontal mouth landmarks."""
    vertical = point_distance(landmarks[top_index], landmarks[bottom_index])
    horizontal = point_distance(landmarks[left_index], landmarks[right_index])

    if horizontal == 0:
        return 0.0

    return vertical / horizontal

