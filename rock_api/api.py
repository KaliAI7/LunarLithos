from datetime import datetime, timezone

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse

from rock_api.schemas import (
    DetectionResponse,
    ReferenceResponse,
    ReferenceSubmission,
)

router = APIRouter(prefix="/api")


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


@router.get("/health")
def health(request: Request):
    camera = getattr(request.app.state, "camera", None)
    return {
        "status": "ok",
        "model": str(request.app.state.settings.model_path),
        "camera_enabled": camera is not None,
    }


@router.get("/classes")
def classes(request: Request):
    return {"classes": request.app.state.detector.class_metadata()}


@router.get("/analog-sites")
def analog_sites(request: Request):
    sites = request.app.state.store.list_analog_sites()
    return {"count": len(sites), "sites": sites}


@router.post("/detect", response_model=DetectionResponse)
async def detect(
    request: Request,
    file: UploadFile = File(...),
    site: str | None = Form(default=None),
    latitude: float | None = Form(default=None, ge=-90, le=90),
    longitude: float | None = Form(default=None, ge=-180, le=180),
):
    settings = request.app.state.settings
    contents = await file.read(settings.max_upload_bytes + 1)
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploaded image is too large")
    image = cv2.imdecode(np.frombuffer(contents, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image")

    inference = request.app.state.detector.predict(image)
    return request.app.state.store.add_observation(
        inference,
        source="api",
        site=site,
        latitude=latitude,
        longitude=longitude,
    )


@router.get("/observations")
def observations(
    request: Request,
    site: str | None = None,
    class_name: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    return request.app.state.store.list_observations(
        site=site,
        class_name=class_name,
        since=_iso_utc(since),
        until=_iso_utc(until),
        limit=limit,
        offset=offset,
    )


@router.delete("/observations/{observation_id}")
def delete_observation(
    request: Request,
    observation_id: int = Path(ge=1),
):
    if not request.app.state.store.delete_observation(observation_id):
        raise HTTPException(status_code=404, detail="Observation not found")
    return {"deleted": True, "observation_id": observation_id}


@router.get("/summary")
def summary(
    request: Request,
    site: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
):
    return request.app.state.store.summary(
        site=site,
        since=_iso_utc(since),
        until=_iso_utc(until),
    )


@router.post("/reference-data", response_model=ReferenceResponse)
def add_reference_data(request: Request, reference: ReferenceSubmission):
    return request.app.state.store.add_reference(
        dataset_name=reference.dataset_name,
        counts=reference.counts,
        site=reference.site,
        latitude=reference.latitude,
        longitude=reference.longitude,
        observed_at=reference.observed_at,
        notes=reference.notes,
    )


@router.get("/compare")
def compare(
    request: Request,
    site: str | None = None,
    dataset_name: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
):
    return request.app.state.store.compare(
        site=site,
        dataset_name=dataset_name,
        since=_iso_utc(since),
        until=_iso_utc(until),
    )


@router.get("/latest")
def latest(request: Request):
    camera = getattr(request.app.state, "camera", None)
    if camera is None:
        raise HTTPException(status_code=503, detail="Live camera is disabled")
    with camera.lock:
        inference = camera.last_inference
        site = camera.current_site
    if inference is None:
        raise HTTPException(status_code=503, detail="No camera inference is available")
    return {
        "site": site[0],
        "latitude": site[1],
        "longitude": site[2],
        "confidence_threshold": inference.confidence_threshold,
        "total_detections": inference.total_detections,
        "lunar_pct": inference.lunar_pct,
        "mars_pct": inference.mars_pct,
        "class_counts": inference.class_counts,
        "detections": inference.detections,
    }


@router.get("/video")
def video(request: Request):
    camera = getattr(request.app.state, "camera", None)
    if camera is None:
        raise HTTPException(status_code=503, detail="Live camera is disabled")

    def frames():
        last_frame_id = -1
        while True:
            with camera.condition:
                camera.condition.wait_for(
                    lambda: camera.frame_id != last_frame_id,
                    timeout=5,
                )
                jpeg = camera.jpeg
                last_frame_id = camera.frame_id
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                + jpeg
                + b"\r\n"
            )

    return StreamingResponse(
        frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/camera/{action}", response_class=PlainTextResponse)
def camera_action(action: str, request: Request):
    camera = getattr(request.app.state, "camera", None)
    if camera is None:
        raise HTTPException(status_code=503, detail="Live camera is disabled")
    if action == "save":
        return camera.save_sample()
    if action == "site":
        return camera.next_site()
    if action == "confidence-up":
        return camera.change_confidence(+0.05)
    if action == "confidence-down":
        return camera.change_confidence(-0.05)
    raise HTTPException(status_code=404, detail="Unknown camera action")
