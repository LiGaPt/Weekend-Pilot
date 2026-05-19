from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.observability import (
    InternalObservabilityRunNotFoundError,
    InternalObservabilityRunSummary,
    InternalObservabilityService,
)


router = APIRouter()


@router.get("/internal/runs/{run_id}/observability", response_model=InternalObservabilityRunSummary)
def get_internal_run_observability(
    run_id: UUID,
    db: Session = Depends(get_db),
) -> InternalObservabilityRunSummary:
    try:
        return InternalObservabilityService(db).get_run_summary(run_id)
    except InternalObservabilityRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Observability run was not found.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal observability request failed.") from exc
