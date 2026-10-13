from datetime import UTC, datetime, timedelta

from mealie.core.config import get_app_settings
from mealie.core.exceptions import UserLockedOut
from mealie.core.security.hasher import get_hasher
from mealie.core.security.tokens import create_access_token
from mealie.db.models.tortoise_models import User
from mealie.schema.user.auth import CredentialsRequest

FAKE_PASSWORD_HASH = "$2b$12$JdHtJOlkPFwyxdjdygEzPOtYmdQF5/R5tHxw5Tq8pxjubyLqdIX5i"


async def authenticate_credentials(data: CredentialsRequest) -> tuple[str, timedelta] | None:
    settings = get_app_settings()
    user = await User.filter(username__iexact=data.username).first()
    if user is None:
        user = await User.filter(email__iexact=data.username).first()

    if user is None:
        _verify_fake_password(data.password)
        return None

    if user.auth_method != "MEALIE":
        _verify_fake_password(data.password)
        return None

    if user.login_attemps >= settings.SECURITY_MAX_LOGIN_ATTEMPTS or _is_locked(user.locked_at):
        raise UserLockedOut()

    if not user.password or not get_hasher().verify(data.password, user.password):
        user.login_attemps += 1
        if user.login_attemps >= settings.SECURITY_MAX_LOGIN_ATTEMPTS:
            user.locked_at = datetime.now(UTC).replace(tzinfo=None)
        await user.save(update_fields=["login_attemps", "locked_at"])
        return None

    user.login_attemps = 0
    await user.save(update_fields=["login_attemps"])
    return create_access_token({"sub": str(user.id), "rme": data.remember_me})


def _is_locked(locked_at: datetime | None) -> bool:
    if locked_at is None:
        return False
    settings = get_app_settings()
    now = datetime.now(UTC).replace(tzinfo=None)
    expires_at = locked_at + timedelta(hours=settings.SECURITY_USER_LOCKOUT_TIME)
    return expires_at > now


def _verify_fake_password(password: str) -> None:
    get_hasher().verify(password, FAKE_PASSWORD_HASH)
