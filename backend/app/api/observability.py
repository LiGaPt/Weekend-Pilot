from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.benchmark.internal_summary import (
    ReleaseGateBenchmarkSummary,
    ReleaseGateBenchmarkSummaryInvalidError,
    ReleaseGateBenchmarkSummaryNotFoundError,
    load_latest_release_gate_summary,
)
from backend.app.db.session import get_db
from backend.app.observability import (
    InternalObservabilityRunNotFoundError,
    InternalObservabilityRunSummary,
    InternalObservabilityService,
)


router = APIRouter()


@router.get(
    "/internal/benchmarks/release-gate-v1/summary",
    response_model=ReleaseGateBenchmarkSummary,
)
def get_release_gate_benchmark_summary() -> ReleaseGateBenchmarkSummary:
    try:
        return load_latest_release_gate_summary()
    except ReleaseGateBenchmarkSummaryNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Latest release_gate_v1 benchmark summary was not found. Run python scripts/run_benchmark_release_gate.py first.",
        ) from exc
    except ReleaseGateBenchmarkSummaryInvalidError as exc:
        raise HTTPException(
            status_code=500,
            detail="Latest release_gate_v1 benchmark summary is invalid.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal benchmark summary request failed.") from exc


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
