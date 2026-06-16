from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.memory_control import (
    MemoryControlListResponse,
    MemoryControlMutationResponse,
    MemoryControlRequest,
    MemoryUserControlService,
    MemoryUserControlServiceError,
)


router = APIRouter()


@router.get(
    "/internal/users/{user_id}/memory",
    response_model=MemoryControlListResponse,
)
def list_user_memory(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> MemoryControlListResponse:
    service = MemoryUserControlService(db)
    try:
        return service.list_items(user_id)
    except MemoryUserControlServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal memory request failed.") from exc


@router.post(
    "/internal/users/{user_id}/memory/{memory_id}/control",
    response_model=MemoryControlMutationResponse,
)
def control_user_memory(
    user_id: UUID,
    memory_id: UUID,
    request: MemoryControlRequest,
    db: Session = Depends(get_db),
) -> MemoryControlMutationResponse:
    service = MemoryUserControlService(db)
    try:
        response = service.apply_action(user_id, memory_id, request.action, request.reason)
        db.commit()
        return response
    except MemoryUserControlServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal memory control request failed.") from exc
