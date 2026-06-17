"""EstudioHC Dashboard — static file server with API proxy."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).parent.parent / "static"
API_URL = os.getenv("API_URL", "http://estudiohc-api:5050")

app = FastAPI(title="EstudioHC Hub", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy_api(path: str, request: Request):
    target_url = f"{API_URL}/api/{path}"
    body = await request.body()

    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method=request.method,
            url=target_url,
            content=body,
            headers={k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")},
            params=request.query_params,
            timeout=240,
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
    )


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/projeto.html")
async def projeto():
    return FileResponse(str(STATIC_DIR / "projeto.html"))


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def main():
    port = int(os.getenv("PORT", "8585"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()