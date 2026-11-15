from dataclasses import dataclass
from threading import Lock
from typing import Any

import cv2
from ultralytics import YOLO

from rock_api.config import Settings


@dataclass
class Inference:
    confidence_threshold: float
    total_detections: int
    lunar_pct: float
    mars_pct: float
    class_counts: list[dict[str, Any]]
    detections: list[dict[str, Any]]


class RockDetector:
    def __init__(self, settings: Settings):
        if not settings.model_path.is_file():
            raise FileNotFoundError(f"Model file does not exist: {settings.model_path}")
        self.settings = settings
        self.model = YOLO(str(settings.model_path))
        self.names = self._normalize_names(self.model.names)
        self.device = (
            int(settings.device) if settings.device.isdigit() else settings.device
        )
        self._inference_lock = Lock()

    @staticmethod
    def _normalize_names(names: Any) -> dict[int, str]:
        if isinstance(names, dict):
            return {int(class_id): str(name) for class_id, name in names.items()}
        return {class_id: str(name) for class_id, name in enumerate(names)}

    def class_metadata(self) -> list[dict[str, str]]:
        return [
            {"class_name": name, "category": self._category(name)}
            for _, name in sorted(self.names.items())
        ]

    def _category(self, class_name: str) -> str:
        if class_name in self.settings.lunar_classes:
            return "lunar"
        if class_name in self.settings.mars_classes:
            return "mars"
        if class_name in self.settings.earth_classes:
            return "earth"
        return "other"

    def predict(self, image, confidence: float | None = None) -> Inference:
        threshold = self.settings.confidence if confidence is None else confidence
        with self._inference_lock:
            result = self.model.predict(
                image,
                conf=threshold,
                imgsz=self.settings.image_size,
                device=self.device,
                verbose=False,
            )[0]

        detections = []
        counts = {name: 0 for name in self.names.values()}
        confidence_sums = {name: 0.0 for name in self.names.values()}
        lunar_score = 0.0
        mars_score = 0.0
        total_score = 0.0

        for box in result.boxes:
            class_id = int(box.cls[0])
            class_name = self.names[class_id]
            score = float(box.conf[0])
            coordinates = [float(value) for value in box.xyxy[0].tolist()]
            detections.append(
                {
                    "class_name": class_name,
                    "confidence": score,
                    "bbox": coordinates,
                }
            )
            counts[class_name] += 1
            confidence_sums[class_name] += score
            total_score += score
            if class_name in self.settings.lunar_classes:
                lunar_score += score
            if class_name in self.settings.mars_classes:
                mars_score += score

        class_counts = [
            {
                "class_name": name,
                "category": self._category(name),
                "count": counts[name],
                "confidence_sum": confidence_sums[name],
            }
            for name in sorted(counts)
        ]
        return Inference(
            confidence_threshold=threshold,
            total_detections=len(detections),
            lunar_pct=100 * lunar_score / total_score if total_score else 0.0,
            mars_pct=100 * mars_score / total_score if total_score else 0.0,
            class_counts=class_counts,
            detections=detections,
        )

    def annotate(self, image, inference: Inference):
        annotated = image.copy()
        for detection in inference.detections:
            x1, y1, x2, y2 = (int(value) for value in detection["bbox"])
            label = (
                f'{detection["class_name"]} '
                f'{detection["confidence"]:.2f}'
            )
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (80, 220, 100), 2)
            cv2.putText(
                annotated,
                label,
                (x1, max(y1 - 8, 18)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (80, 220, 100),
                2,
                cv2.LINE_AA,
            )
        return annotated
