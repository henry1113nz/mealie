from fastapi import HTTPException, status

from mealie.core.security import hash_password, url_safe_token
from mealie.db.models.tortoise_models import PasswordResetModel, User
from mealie.schema.user.user_passwords import SavePasswordResetToken
from mealie.services._base_service import BaseService
from mealie.services.email import EmailService


class PasswordResetService(BaseService):
    async def generate_reset_token(self, email: str) -> SavePasswordResetToken | None:
        user = await User.filter(email__iexact=email).first()

        if user is None:
            self.logger.error(f"failed to create password reset for {email=}: user doesn't exists")
            # Do not raise exception here as we don't want to confirm to the client that the Email doesn't exists
            return None
        if user.auth_method == "LDAP":
            self.logger.error(f"failed to create password reset for {email=}: user controlled by LDAP")
            return None

        token = url_safe_token()
        token_entry = await PasswordResetModel.create(user=user, token=token)
        return SavePasswordResetToken(user_id=user.id, token=token_entry.token)

    async def send_reset_email(self, email: str, accept_language: str | None = None) -> None:
        token_entry = await self.generate_reset_token(email)
        if token_entry is None:
            return None

        email_service = EmailService(locale=accept_language)
        reset_url = f"{self.settings.BASE_URL}/reset-password/?token={token_entry.token}"

        try:
            email_service.send_forgot_password(email, reset_url)
        except Exception as e:
            self.logger.error(f"failed to send reset email: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to send reset email") from e

    async def reset_password(self, token: str, new_password: str) -> None:
        token_entry = await PasswordResetModel.filter(token=token).first()
        if token_entry is None:
            self.logger.error("failed to reset password: invalid token")
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid token")

        user = await token_entry.user
        password_hash = hash_password(new_password)
        user.password = password_hash
        await user.save(update_fields=["password"])

        if user.password != password_hash:
            self.logger.error("failed to reset password: invalid password")
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid password")

        await token_entry.delete()
