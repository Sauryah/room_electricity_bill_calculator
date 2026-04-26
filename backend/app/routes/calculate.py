"""Protected /calculate route — splits a bill across roommates by days present."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, conlist

from app.core.security import get_current_user

router = APIRouter(tags=["calculate"])


class Roommate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    days: float = Field(..., ge=0)


class CalculateRequest(BaseModel):
    total_bill: float = Field(..., gt=0)
    total_days: int = Field(..., ge=1, le=31)
    roommates: conlist(Roommate, min_length=1)


class RoommateShare(BaseModel):
    name: str
    days: float
    percentage: float
    amount: float


class CalculateResponse(BaseModel):
    total_bill: float
    total_days: int
    total_days_present: float
    roommates: List[RoommateShare]


@router.post("/calculate", response_model=CalculateResponse)
def calculate(
    payload: CalculateRequest,
    current_user: dict = Depends(get_current_user),
) -> CalculateResponse:
    # Validate per-roommate days
    for r in payload.roommates:
        if r.days > payload.total_days:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Days for '{r.name}' cannot exceed total_days ({payload.total_days})",
            )

    total_days_present = sum(r.days for r in payload.roommates)
    if total_days_present <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Total days present cannot be zero",
        )

    shares: List[RoommateShare] = []
    for r in payload.roommates:
        ratio = r.days / total_days_present
        shares.append(
            RoommateShare(
                name=r.name,
                days=r.days,
                percentage=round(ratio * 100, 4),
                amount=round(ratio * payload.total_bill, 2),
            )
        )

    return CalculateResponse(
        total_bill=round(payload.total_bill, 2),
        total_days=payload.total_days,
        total_days_present=total_days_present,
        roommates=shares,
    )
