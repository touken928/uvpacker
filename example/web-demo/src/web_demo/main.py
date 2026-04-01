from __future__ import annotations

import mimetypes
from importlib import resources
from pathlib import PurePosixPath

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response


PACKAGE_NAME = "web_demo"

app = FastAPI(title="uvpack web demo")


def _resource_file(*parts: str):
    resource = resources.files(PACKAGE_NAME)
    for part in parts:
        resource = resource.joinpath(part)
    return resource


def _safe_static_parts(asset_path: str) -> tuple[str, ...]:
    path = PurePosixPath(asset_path)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise HTTPException(status_code=404, detail="Asset not found")
    return tuple(path.parts)


@app.get("/api/hello", response_class=JSONResponse)
async def api_hello() -> dict[str, str]:
    return {"message": "Hello from uvpack web demo!"}


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(
        _resource_file("templates", "index.html").read_text(encoding="utf-8"),
    )


@app.get("/static/{asset_path:path}")
async def static_asset(asset_path: str) -> Response:
    resource = _resource_file("static", *_safe_static_parts(asset_path))
    if not resource.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")

    media_type = mimetypes.guess_type(asset_path)[0] or "application/octet-stream"
    return Response(resource.read_bytes(), media_type=media_type)


def main() -> int:
    """Entry point used by [project.scripts]."""
    import uvicorn

    uvicorn.run("web_demo.main:app", host="127.0.0.1", port=8000, reload=False)
    return 0

