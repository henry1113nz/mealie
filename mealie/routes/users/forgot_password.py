from typing import Annotated

from fastapi import APIRouter, Header

from mealie.schema.user.user_passwords import ForgotPassword, ResetPassword
from mealie.services.user_services.password_reset_service import PasswordResetService

router = APIRouter(prefix="")


@router.post("/forgot-password")
async def forgot_password(
    email: ForgotPassword,
    accept_language: Annotated[str | None, Header()] = None,
):
    """Sends an email with a reset link to the user"""
    f_service = PasswordResetService()
    return await f_service.send_reset_email(email.email, accept_language)


@router.post("/reset-password")
async def reset_password(reset_password: ResetPassword):
    """Resets the user password"""
    f_service = PasswordResetService()
    return await f_service.reset_password(reset_password.token, reset_password.password)
