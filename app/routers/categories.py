from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category

router = APIRouter(prefix="/categories")


def _redirect(msg: str, msg_type: str = "success") -> RedirectResponse:
    return RedirectResponse(url=f"/categories?msg={msg}&msg_type={msg_type}", status_code=303)


@router.post("/create")
def create_category(name: str = Form(...), color: str = Form("#6d6dfb"), db: Session = Depends(get_db)):
    name = name.strip()
    if not name:
        return _redirect("카테고리 이름을 입력하세요", "error")
    if db.query(Category).filter_by(name=name).first():
        return _redirect("이미 존재하는 카테고리입니다", "error")
    db.add(Category(name=name, color=color))
    db.commit()
    return _redirect("카테고리가 추가되었습니다")


@router.post("/{category_id}/edit")
def edit_category(category_id: int, name: str = Form(...), color: str = Form(...), db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if not category:
        return _redirect("카테고리를 찾을 수 없습니다", "error")
    category.name = name.strip() or category.name
    category.color = color
    db.commit()
    return _redirect("카테고리가 수정되었습니다")


@router.post("/{category_id}/delete")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if not category:
        return _redirect("카테고리를 찾을 수 없습니다", "error")
    if category.is_system:
        return _redirect("기본 카테고리는 삭제할 수 없습니다", "error")
    db.delete(category)
    db.commit()
    return _redirect("카테고리가 삭제되었습니다")
