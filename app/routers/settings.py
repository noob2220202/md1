from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from .. import settings_store

router = APIRouter(prefix="/settings")


@router.post("/auto-wipe")
async def update_auto_wipe(request: Request):
    form = await request.form()
    enabled = form.get("auto_wipe_on_add") == "on"
    settings_store.set_setting("auto_wipe_on_add", "true" if enabled else "false")
    msg = "계정 추가 시 자동 초기화가 켜졌습니다" if enabled else "계정 추가 시 자동 초기화가 꺼졌습니다"
    return RedirectResponse(url=f"/settings?msg={msg}&msg_type=success", status_code=303)
