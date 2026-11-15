#!/usr/bin/env python3
"""Start the LunarLens web application."""

import uvicorn

from rock_api.config import get_settings
from rock_api.main import app


if __name__ == "__main__":
    settings = get_settings()
    print(f"[INFO] Open http://localhost:{settings.port}")
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
