from fastapi import HTTPException, status
from sqlalchemy.orm.session import Session
from tortoise.transactions import in_transaction

from mealie.core.config import get_app_settings
from mealie.core.security import hash_password, url_safe_token
from mealie.db.models.users.users import AuthMethod
from mealie.db.tortoise_models import AuthMethod as TortoiseAuthMethod
from mealie.db.tortoise_models import User
from mealie.db.tortoise_models.remaining import PasswordResetModel
from mealie.repos.all_repositories import get_repositories
from mealie.repos.tortoise_user import TortoiseAuthRepository, TortoiseUserRepository
from mealie.schema.user.user_passwords import SavePasswordResetToken
from mealie.services._base_service import BaseService
from mealie.services.email import EmailService


class PasswordResetService(BaseService):
    def __init__(self, session: Session) -> None:
        self.db = get_repositories(session, group_id=None, household_id=None)
        super().__init__()

    def generate_reset_token(self, email: str) -> SavePasswordResetToken | None:
        user = self.db.users.get_one(email, "email", any_case=True)

        if user is None:
            self.logger.error(f"failed to create password reset for {email=}: user doesn't exists")
            # Do not raise exception here as we don't want to confirm to the client that the Email doesn't exists
            return None
        elif user.auth_method == AuthMethod.LDAP:
            self.logger.error(f"failed to create password reset for {email=}: user controlled by LDAP")
            return None

        # Create Reset Token
        token = url_safe_token()

        save_token = SavePasswordResetToken(user_id=user.id, token=token)

        return self.db.tokens_pw_reset.create(save_token)

    def send_reset_email(self, email: str, accept_language: str | None = None):
        token_entry = self.generate_reset_token(email)

        if token_entry is None:
            return None

        # Send Email
        email_servive = EmailService(locale=accept_language)
        reset_url = f"{self.settings.BASE_URL}/reset-password/?token={token_entry.token}"

        try:
            email_servive.send_forgot_password(email, reset_url)
        except Exception as e:
            self.logger.error(f"failed to send reset email: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to send reset email") from e

    def reset_password(self, token: str, new_password: str):
        # Validate Token
        token_entry = self.db.tokens_pw_reset.get_one(token, "token")

        if token_entry is None:
            self.logger.error("failed to reset password: invalid token")
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid token")

        user = self.db.users.get_one(token_entry.user_id)
        # Update Password
        password_hash = hash_password(new_password)

        new_user = self.db.users.update_password(user.id, password_hash)
        # Confirm Password
        if new_user.password != password_hash:
            self.logger.error("failed to reset password: invalid password")
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid password")

        # Delete Token from DB
        self.db.tokens_pw_reset.delete(token_entry.token)


class AsyncPasswordResetService(BaseService):
    """Tortoise-backed reset flow; token redemption and password mutation are atomic."""

    def __init__(self) -> None:
        super().__init__()
        self.users = TortoiseUserRepository()
        self.auth = TortoiseAuthRepository()

    async def generate_reset_token(self, email: str) -> SavePasswordResetToken | None:
        user = await self.users.get_one(email, "email", any_case=True)
        if user is None or getattr(user.auth_method, "name", None) == TortoiseAuthMethod.LDAP.name:
            self.logger.error(f"failed to create password reset for {email=}: user unavailable")
            return None
        token = url_safe_token()
        await self.auth.create_reset_token(user.id, token)
        return SavePasswordResetToken(user_id=user.id, token=token)

    async def send_reset_email(self, email: str, accept_language: str | None = None) -> None:
        token_entry = await self.generate_reset_token(email)
        if token_entry is None:
            return None
        email_service = EmailService(locale=accept_language)
        reset_url = f"{self.settings.BASE_URL}/reset-password/?token={token_entry.token}"
        try:
            email_service.send_forgot_password(email, reset_url)
        except Exception as error:
            self.logger.error(f"failed to send reset email: {error}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to send reset email") from error

    async def reset_password(self, token: str, new_password: str) -> None:
        password_hash = hash_password(new_password)
        async with in_transaction() as connection:
            token_entry = await PasswordResetModel.filter(token=token).using_db(connection).first()
            if token_entry is None:
                self.logger.error("failed to reset password: invalid token")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
            user = await User.filter(id=token_entry.user_id).using_db(connection).first()
            if user is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
            if get_app_settings().IS_DEMO and user.email == get_app_settings()._DEFAULT_EMAIL.strip().lower():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid password")
            user.password = password_hash
            from datetime import UTC, datetime

            user.tokens_valid_after = datetime.now(UTC).replace(microsecond=0)
            await user.save(using_db=connection, update_fields=["password", "tokens_valid_after"])
            await token_entry.delete(using_db=connection)
