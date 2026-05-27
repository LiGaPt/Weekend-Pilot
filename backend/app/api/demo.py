from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from redis import Redis
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.db.session import get_db
from backend.app.demo import (
    DemoClarifyRunRequest,
    DemoConfirmRunRequest,
    DemoDeclineRunRequest,
    DemoReplanRunRequest,
    DemoRunSummary,
    DemoServiceError,
    DemoStartRunRequest,
    DemoWorkflowService,
)
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache, RedisKeyBuilder, get_redis_client


router = APIRouter()
T = TypeVar("T")


def _build_service(
    db: Session,
    redis_client: Redis,
    settings: Settings,
) -> DemoWorkflowService:
    keys = RedisKeyBuilder(prefix=f"{settings.app_name}:{settings.app_env}")
    return DemoWorkflowService(
        session=db,
        cache=JsonRedisCache(redis_client, keys),
        rate_limiter=FixedWindowRateLimiter(redis_client, keys),
        trace_buffer_path=settings.local_trace_buffer_path,
        workflow_settings=settings,
    )


def _call(db: Session, fn: Callable[[], T]) -> T:
    try:
        return fn()
    except DemoServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Demo workflow request failed.") from exc


@router.post("/demo/runs", response_model=DemoRunSummary)
def start_demo_run(
    request: DemoStartRunRequest,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
) -> DemoRunSummary:
    service = _build_service(db, redis_client, settings)
    return _call(db, lambda: service.start_run(request))


@router.get("/demo/runs/{run_id}", response_model=DemoRunSummary)
def get_demo_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
) -> DemoRunSummary:
    service = _build_service(db, redis_client, settings)
    return _call(db, lambda: service.get_run(run_id))


@router.post("/demo/runs/{run_id}/clarify", response_model=DemoRunSummary)
def clarify_demo_run(
    run_id: UUID,
    request: DemoClarifyRunRequest,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
) -> DemoRunSummary:
    service = _build_service(db, redis_client, settings)
    return _call(db, lambda: service.clarify_run(run_id, request))


@router.post("/demo/runs/{run_id}/replan", response_model=DemoRunSummary)
def replan_demo_run(
    run_id: UUID,
    request: DemoReplanRunRequest,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
) -> DemoRunSummary:
    service = _build_service(db, redis_client, settings)
    return _call(db, lambda: service.replan_run(run_id, request))


@router.post("/demo/runs/{run_id}/confirm", response_model=DemoRunSummary)
def confirm_demo_run(
    run_id: UUID,
    request: DemoConfirmRunRequest,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
) -> DemoRunSummary:
    service = _build_service(db, redis_client, settings)
    return _call(db, lambda: service.confirm_run(run_id, request))


@router.post("/demo/runs/{run_id}/decline", response_model=DemoRunSummary)
def decline_demo_run(
    run_id: UUID,
    request: DemoDeclineRunRequest,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
) -> DemoRunSummary:
    service = _build_service(db, redis_client, settings)
    return _call(db, lambda: service.decline_run(run_id, request))
