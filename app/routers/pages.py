from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import settings_store
from ..database import get_db
from ..models import Account, Category
from ..templating import templates

router = APIRouter()

TRUST_LABELS = {
    "clean": ("정상", "trust-clean"),
    "limited": ("제한", "trust-limited"),
    "banned": ("차단", "trust-banned"),
    "unknown": ("미확인", "trust-unknown"),
}


@router.get("/")
def dashboard(
    request: Request,
    category: Optional[int] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Account)
    if category:
        query = query.filter(Account.categories.any(Category.id == category))
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Account.first_name.like(like),
                Account.last_name.like(like),
                Account.username.like(like),
                Account.phone.like(like),
            )
        )
    accounts = query.order_by(Account.created_at.desc()).all()
    categories = db.query(Category).order_by(Category.name).all()

    stats = {
        "total": db.query(Account).count(),
        "clean": db.query(Account).filter(Account.trust_status == "clean").count(),
        "limited": db.query(Account).filter(Account.trust_status == "limited").count(),
        "banned": db.query(Account).filter(Account.trust_status == "banned").count(),
    }

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "accounts": accounts,
            "categories": categories,
            "stats": stats,
            "trust_labels": TRUST_LABELS,
            "active_category": category,
            "q": q or "",
            "auto_wipe": settings_store.get_bool_setting("auto_wipe_on_add"),
        },
    )


@router.get("/accounts/{account_id}")
def account_detail(account_id: int, request: Request, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    categories = db.query(Category).order_by(Category.name).all()
    return templates.TemplateResponse(
        "account_detail.html",
        {
            "request": request,
            "account": account,
            "categories": categories,
            "trust_labels": TRUST_LABELS,
        },
    )


@router.get("/categories")
def categories_page(request: Request, db: Session = Depends(get_db)):
    categories = db.query(Category).order_by(Category.name).all()
    return templates.TemplateResponse("categories.html", {"request": request, "categories": categories})


@router.get("/settings")
def settings_page(request: Request):
    from .. import settings_store
    from ..config import settings as cfg

    configured = bool(cfg.telegram_api_id and cfg.telegram_api_hash)
    auto_wipe = settings_store.get_bool_setting("auto_wipe_on_add")
    return templates.TemplateResponse(
        "settings.html", {"request": request, "configured": configured, "auto_wipe": auto_wipe}
    )
