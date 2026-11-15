import threading
import time
from datetime import datetime

import cv2
import numpy as np

from rock_api.config import Settings
from rock_api.detector import Inference, RockDetector
from rock_api.storage import ObservationStore

SITES = [
    ("Pinacate", 31.77, -113.50),
    ("Samalayuca Dunes", 31.35, -106.48),
    ("UTD Laboratory", 31.69, -106.42),
]


def draw_text(image, text, position, scale=0.8, color=(255, 255, 255)):
    cv2.putText(
        image, text, position, cv2.FONT_HERSHEY_SIMPLEX, scale,
        (0, 0, 0), 4, cv2.LINE_AA,
    )
    cv2.putText(
        image, text, position, cv2.FONT_HERSHEY_SIMPLEX, scale,
        color, 2, cv2.LINE_AA,
    )


def open_camera(settings: Settings):
    for backend in (cv2.CAP_V4L2, cv2.CAP_ANY):
        try:
            capture = cv2.VideoCapture(settings.camera_index, backend)
        except Exception:
            continue
        if capture is not None and capture.isOpened():
            capture.set(
                cv2.CAP_PROP_FOURCC,
                cv2.VideoWriter_fourcc(*"MJPG"),
            )
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, settings.frame_width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.frame_height)
            capture.set(cv2.CAP_PROP_FPS, 30)
            return capture
        if capture is not None:
            capture.release()
    return cv2.VideoCapture(settings.camera_index)


class CameraService:
    def __init__(
        self,
        settings: Settings,
        detector: RockDetector,
        store: ObservationStore,
    ):
        self.settings = settings
        self.detector = detector
        self.store = store
        self.condition = threading.Condition()
        self.lock = threading.Lock()
        self.confidence = settings.confidence
        self.site_index = 0
        self.frame_id = 0
        self.jpeg = self._placeholder("Starting camera...")
        self.last_frame = None
        self.last_inference: Inference | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _placeholder(self, message: str) -> bytes:
        image = np.zeros(
            (self.settings.frame_height, self.settings.frame_width, 3),
            dtype=np.uint8,
        )
        draw_text(
            image,
            message,
            (40, self.settings.frame_height // 2),
            1.0,
            (0, 200, 255),
        )
        ok, buffer = cv2.imencode(
            ".jpg",
            image,
            [cv2.IMWRITE_JPEG_QUALITY, self.settings.jpeg_quality],
        )
        if not ok:
            raise RuntimeError("Could not encode the camera placeholder image")
        return buffer.tobytes()

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=3)

    def _publish(self, jpeg: bytes):
        with self.condition:
            self.jpeg = jpeg
            self.frame_id += 1
            self.condition.notify_all()

    def _run(self):
        capture = None
        previous_frame_time = time.time()
        fps = 0.0
        while not self._stop.is_set():
            if capture is None or not capture.isOpened():
                capture = open_camera(self.settings)
                if not capture.isOpened():
                    capture.release()
                    capture = None
                    self._publish(
                        self._placeholder(
                            f"Camera unavailable (index {self.settings.camera_index})"
                        )
                    )
                    self._stop.wait(2)
                    continue

            ok, frame = capture.read()
            if not ok:
                self._stop.wait(0.03)
                continue

            with self.lock:
                confidence = self.confidence
                site = SITES[self.site_index]
            inference = self.detector.predict(frame, confidence)
            annotated = self.detector.annotate(frame, inference)

            now = time.time()
            instant_fps = 1.0 / max(now - previous_frame_time, 1e-6)
            fps = instant_fps if fps == 0 else 0.9 * fps + 0.1 * instant_fps
            previous_frame_time = now
            draw_text(
                annotated,
                f"FPS {fps:.1f}   Confidence >= {confidence:.2f}",
                (20, 40),
                0.8,
                (0, 255, 0),
            )
            draw_text(
                annotated,
                f"Detections: {inference.total_detections}",
                (20, 80),
                0.8,
            )
            draw_text(
                annotated,
                f"Lunar: {inference.lunar_pct:.0f}%   Mars: {inference.mars_pct:.0f}%",
                (20, 120),
                0.9,
                (0, 255, 255),
            )
            draw_text(annotated, f"Site: {site[0]}", (20, 160), 0.7)

            with self.lock:
                self.last_frame = annotated.copy()
                self.last_inference = inference

            encoded, buffer = cv2.imencode(
                ".jpg",
                annotated,
                [cv2.IMWRITE_JPEG_QUALITY, self.settings.jpeg_quality],
            )
            if not encoded:
                raise RuntimeError("Could not encode a camera frame")
            self._publish(buffer.tobytes())

        if capture is not None:
            capture.release()

    def save_sample(self) -> str:
        with self.lock:
            frame = None if self.last_frame is None else self.last_frame.copy()
            inference = self.last_inference
            site = SITES[self.site_index]
        if frame is None or inference is None:
            return "No camera frame is available yet"
        if inference.total_detections == 0:
            return "No rocks were detected; sample was not saved"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.settings.samples_dir.mkdir(parents=True, exist_ok=True)
        image_path = self.settings.samples_dir / f"{timestamp}.jpg"
        if not cv2.imwrite(str(image_path), frame):
            raise OSError(f"Could not save sample image: {image_path}")
        observation = self.store.add_observation(
            inference,
            source="camera",
            site=site[0],
            latitude=site[1],
            longitude=site[2],
        )
        return (
            f"Saved {image_path.name} "
            f"(observation {observation['observation_id']}, {site[0]})"
        )

    def next_site(self) -> str:
        with self.lock:
            self.site_index = (self.site_index + 1) % len(SITES)
            return f"Site: {SITES[self.site_index][0]}"

    def change_confidence(self, delta: float) -> str:
        with self.lock:
            self.confidence = round(
                min(0.95, max(0.05, self.confidence + delta)), 2
            )
            return f"Confidence: {self.confidence:.2f}"
