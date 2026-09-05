from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from auth.dependencies import CurrentAuth, get_current_auth, require_csrf
from db.models import PaymentOrder, User
from db.session import get_db_session
from fastapi import APIRouter, Depends, HTTPException, status
from settings import get_settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/billing", tags=["Billing"])
settings = get_settings()


def payment_order_response(
    order: PaymentOrder, *, email: str | None = None, include_admin: bool = False
) -> dict:
    response = {
        "id": str(order.id),
        "reference_code": order.reference_code,
        "amount_minor": order.amount_minor,
        "currency": order.currency,
        "premium_days": order.premium_days,
        "recipient": order.recipient,
        "iban": order.iban,
        "status": order.status,
        "created_at": order.created_at.isoformat(),
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "cancelled_at": order.cancelled_at.isoformat()
        if order.cancelled_at
        else None,
    }
    if email is not None:
        response["user_email"] = email
    if include_admin:
        response["admin_note"] = order.admin_note
    return response


@router.get("/manual")
async def manual_payment_summary(
    current: Annotated[CurrentAuth, Depends(get_current_auth)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    orders = (
        await db.scalars(
            select(PaymentOrder)
            .where(PaymentOrder.user_id == current.user.id)
            .order_by(PaymentOrder.created_at.desc())
            .limit(10)
        )
    ).all()
    return {
        "enabled": settings.manual_payments_enabled,
        "offer": {
            "amount_minor": settings.manual_premium_amount_grosze,
            "currency": "PLN",
            "premium_days": settings.manual_premium_days,
        }
        if settings.manual_payments_enabled
        else None,
        "orders": [payment_order_response(order) for order in orders],
    }


@router.post("/manual/orders", status_code=status.HTTP_201_CREATED)
async def create_manual_payment_order(
    current: Annotated[CurrentAuth, Depends(require_csrf)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    if not settings.manual_payments_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Płatności przelewem nie są jeszcze dostępne.",
        )

    # Serialize creation per user so repeated clicks cannot create two pending orders.
    await db.scalar(select(User).where(User.id == current.user.id).with_for_update())
    pending = await db.scalar(
        select(PaymentOrder).where(
            PaymentOrder.user_id == current.user.id,
            PaymentOrder.status == "pending",
        )
    )
    if pending is not None:
        return payment_order_response(pending)

    order = PaymentOrder(
        user_id=current.user.id,
        reference_code=f"RC-{uuid.uuid4().hex[:10].upper()}",
        amount_minor=settings.manual_premium_amount_grosze,
        currency="PLN",
        premium_days=settings.manual_premium_days,
        recipient=settings.manual_payment_recipient,
        iban=settings.manual_payment_iban,
        status="pending",
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return payment_order_response(order)
