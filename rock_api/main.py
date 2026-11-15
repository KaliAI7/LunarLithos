from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse

from rock_api.api import router
from rock_api.camera import CameraService
from rock_api.config import get_settings
from rock_api.detector import RockDetector
from rock_api.frontend import PAGE
from rock_api.storage import ObservationStore

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    app.state.detector = RockDetector(settings)
    app.state.store = ObservationStore(settings.database_path)
    app.state.camera = None
    camera = None
    if settings.camera_enabled:
        camera = CameraService(settings, app.state.detector, app.state.store)
        app.state.camera = camera
        camera.start()
    try:
        yield
    finally:
        if camera is not None:
            camera.stop()


app = FastAPI(title="LunarLens Rock Detection API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


@app.get("/video")
def legacy_video():
    raise HTTPException(
        status_code=307,
        detail="Use /api/video for the camera stream",
        headers={"Location": "/api/video"},
    )


@app.post("/do/{action}", response_class=PlainTextResponse)
def legacy_camera_action(action: str):
    action_map = {
        "save": "save",
        "site": "site",
        "conf_up": "confidence-up",
        "conf_down": "confidence-down",
    }
    if action not in action_map:
        raise HTTPException(status_code=404, detail="Unknown camera action")
    raise HTTPException(
        status_code=307,
        detail="Use /api/camera/{action}",
        headers={"Location": f"/api/camera/{action_map[action]}"},
    )


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
