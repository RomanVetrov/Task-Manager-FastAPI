from __future__ import annotations

from fastapi import APIRouter, Response

from app.metrics import render_metrics

router = APIRouter(include_in_schema=False)


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    content, media_type = render_metrics()
    return Response(content=content, media_type=media_type)
