import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _csv_values(name: str, default: str) -> frozenset[str]:
    return frozenset(
        value.strip()
        for value in os.getenv(name, default).split(",")
        if value.strip()
    )


@dataclass(frozen=True)
class Settings:
    model_path: Path
    camera_index: int
    frame_width: int
    frame_height: int
    confidence: float
    image_size: int
    device: str
    host: str
    port: int
    jpeg_quality: int
    camera_enabled: bool
    database_path: Path
    samples_dir: Path
    max_upload_bytes: int
    cors_origins: tuple[str, ...]
    lunar_classes: frozenset[str]
    mars_classes: frozenset[str]
    earth_classes: frozenset[str]


def get_settings() -> Settings:
    model_value = os.getenv("MODEL_PATH", "model.pt")
    database_value = os.getenv("DATABASE_PATH", "samples/observations.sqlite3")
    samples_value = os.getenv("SAMPLES_DIR", "samples")
    origins = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
        ).split(",")
        if origin.strip()
    )
    return Settings(
        model_path=(PROJECT_ROOT / model_value).resolve()
        if not Path(model_value).is_absolute()
        else Path(model_value),
        camera_index=int(os.getenv("CAMERA_INDEX", "0")),
        frame_width=int(os.getenv("FRAME_W", "1280")),
        frame_height=int(os.getenv("FRAME_H", "720")),
        confidence=float(os.getenv("CONF", "0.40")),
        image_size=int(os.getenv("IMGSZ", "640")),
        device=os.getenv("DEVICE", "0"),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8080")),
        jpeg_quality=int(os.getenv("JPEG_QUALITY", "80")),
        camera_enabled=os.getenv("CAMERA_ENABLED", "true").lower()
        in {"1", "true", "yes", "on"},
        database_path=(PROJECT_ROOT / database_value).resolve()
        if not Path(database_value).is_absolute()
        else Path(database_value),
        samples_dir=(PROJECT_ROOT / samples_value).resolve()
        if not Path(samples_value).is_absolute()
        else Path(samples_value),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_MB", "15")) * 1024 * 1024,
        cors_origins=origins,
        lunar_classes=_csv_values(
            "LUNAR_CLASSES", "lunar_basalt,anorthosite,lunar_breccia"
        ),
        mars_classes=_csv_values("MARS_CLASSES", "hematite"),
        earth_classes=_csv_values("EARTH_CLASSES", "obsidian,pumice_scoria"),
    )
