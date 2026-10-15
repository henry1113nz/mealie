from typing import Annotated

from fastapi import APIRouter, Depends, Header

from mealie.db.tortoise_setup import require_tortoise_ready
from mealie.schema.user.user_passwords import ForgotPassword, ResetPassword
from mealie.services.user_services.password_reset_service import AsyncPasswordResetService

router = APIRouter(prefix="")


@router.post("/forgot-password")
async def forgot_password(
    email: ForgotPassword,
    _tortoise_ready=Depends(require_tortoise_ready),
    accept_language: Annotated[str | None, Header()] = None,
):
    """Sends an email with a reset link to the user"""
    f_service = AsyncPasswordResetService()
    return await f_service.send_reset_email(email.email, accept_language)


@router.post("/reset-password")
async def reset_password(reset_password: ResetPassword, _tortoise_ready=Depends(require_tortoise_ready)):
    """Resets the user password"""
    f_service = AsyncPasswordResetService()
    return await f_service.reset_password(reset_password.token, reset_password.password)
