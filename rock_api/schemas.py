from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class Detection(BaseModel):
    class_name: str
    confidence: float
    bbox: list[float] = Field(description="Pixel coordinates: x1, y1, x2, y2.")


class ClassCount(BaseModel):
    class_name: str
    category: str
    count: int
    confidence_sum: float


class DetectionResponse(BaseModel):
    observation_id: int
    created_at: datetime
    site: str | None
    latitude: float | None
    longitude: float | None
    confidence_threshold: float
    total_detections: int
    lunar_pct: float
    mars_pct: float
    class_counts: list[ClassCount]
    detections: list[Detection]


class ReferenceSubmission(BaseModel):
    dataset_name: str = Field(min_length=1, max_length=200)
    site: str | None = Field(default=None, max_length=200)
    observed_at: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    counts: dict[str, Annotated[int, Field(ge=0)]] = Field(min_length=1)
    notes: str | None = None


class ReferenceResponse(BaseModel):
    reference_id: int
    dataset_name: str
    site: str | None
    observed_at: datetime
    counts: dict[str, int]
