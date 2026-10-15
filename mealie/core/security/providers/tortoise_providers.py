"""Async authentication providers used by routes after the Stage 8 cutover."""

from __future__ import annotations

import asyncio
import hashlib
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import ldap
import ldap.filter
from authlib.oidc.core import UserInfo

from mealie.core import root_logger
from mealie.core.config import get_app_settings
from mealie.core.exceptions import MissingClaimException, UserLockedOut
from mealie.core.security.hasher import get_hasher
from mealie.core.security.tokens import create_access_token
from mealie.db.tortoise_models import AuthMethod
from mealie.pkgs import cache, img
from mealie.repos.tortoise_user import TortoiseUserRepository
from mealie.schema.user.user import PrivateUser

logger = root_logger.get_logger("tortoise_auth")


def _has_auth_method(user: PrivateUser, method: AuthMethod) -> bool:
    """Compare Tortoise and schema enums by their persisted value."""
    user_method_name = getattr(user.auth_method, "name", None)
    if user_method_name is None:
        user_method_name = str(getattr(user.auth_method, "value", user.auth_method))
    return user_method_name == method.name


class AsyncAuthProvider:
    def __init__(self, data: Any) -> None:
        self.data = data
        self.user: PrivateUser | None = None

    async def try_get_user(self, username: str) -> PrivateUser | None:
        if self.user is None:
            self.user = await TortoiseUserRepository().get_one(username, "username", any_case=True)
            if self.user is None:
                self.user = await TortoiseUserRepository().get_one(username, "email", any_case=True)
        return self.user

    @staticmethod
    def access_token(user: PrivateUser, remember_me: bool = False) -> tuple[str, timedelta]:
        return create_access_token({"sub": str(user.id), "rme": remember_me})


class AsyncCredentialsProvider(AsyncAuthProvider):
    def __init__(self, data: Any) -> None:
        super().__init__(data)
        self.users = TortoiseUserRepository()

    async def authenticate(self) -> tuple[str, timedelta] | None:
        settings = get_app_settings()
        user = await self.try_get_user(self.data.username)
        if not user:
            self.verify_fake_password()
            return None
        if not _has_auth_method(user, AuthMethod.MEALIE):
            self.verify_fake_password()
            logger.warning("Found user with non-Mealie auth method; credentials login is unavailable")
            return None
        if user.login_attemps >= settings.SECURITY_MAX_LOGIN_ATTEMPTS or user.is_locked:
            raise UserLockedOut()
        if not self.verify_password(self.data.password, user.password or ""):
            attempts = user.login_attemps + 1
            updated = await self.users.update(user.id, {"login_attemps": attempts})
            if attempts >= settings.SECURITY_MAX_LOGIN_ATTEMPTS and updated:
                await self.users.update(user.id, {"locked_at": datetime.now(UTC)})
            return None
        user = await self.users.update(user.id, {"login_attemps": 0}) or user
        return self.access_token(user, self.data.remember_me)

    @staticmethod
    def verify_fake_password() -> None:
        get_hasher().verify("abc123cba321", "$2b$12$JdHtJOlkPFwyxdjdygEzPOtYmdQF5/R5tHxw5Tq8pxjubyLqdIX5i")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return get_hasher().verify(plain_password, hashed_password)


class AsyncLDAPProvider(AsyncCredentialsProvider):
    """LDAP authentication with all local database operations remaining async."""

    async def authenticate(self) -> tuple[str, timedelta] | None:
        settings = get_app_settings()
        user = await self.try_get_user(self.data.username)
        if user and not _has_auth_method(user, AuthMethod.LDAP):
            return await super().authenticate()
        attributes = await asyncio.to_thread(self._authenticate_directory)
        if attributes is None:
            return None
        user = await self.try_get_user(self.data.username)
        if user is None:
            user = await self.users.create(
                {
                    "username": attributes["username"],
                    "password": "LDAP",
                    "full_name": attributes["full_name"],
                    "email": attributes["email"],
                    "auth_method": AuthMethod.LDAP,
                    "admin": attributes["admin"],
                    "group": settings.DEFAULT_GROUP,
                    "household": settings.DEFAULT_HOUSEHOLD,
                }
            )
        elif _has_auth_method(user, AuthMethod.LDAP) and user.admin != attributes["admin"]:
            user = await self.users.update(user.id, {"admin": attributes["admin"]}) or user
        if _has_auth_method(user, AuthMethod.LDAP):
            return self.access_token(user, self.data.remember_me)
        return await super().authenticate()

    def _authenticate_directory(self) -> dict[str, Any] | None:
        settings = get_app_settings()
        if not self.data.password:
            logger.error("[LDAP] Empty password is not permitted; refusing to bind")
            return None
        if settings.LDAP_TLS_INSECURE:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
        conn = ldap.initialize(settings.LDAP_SERVER_URL)
        try:
            conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
            conn.set_option(ldap.OPT_REFERRALS, 0)
            if settings.LDAP_TLS_CACERTFILE:
                conn.set_option(ldap.OPT_X_TLS_CACERTFILE, settings.LDAP_TLS_CACERTFILE)
                conn.set_option(ldap.OPT_X_TLS_NEWCTX, 0)
            if settings.LDAP_ENABLE_STARTTLS:
                conn.start_tls_s()
            conn.simple_bind_s(settings.LDAP_QUERY_BIND, settings.LDAP_QUERY_PASSWORD)
            escaped = ldap.filter.escape_filter_chars(self.data.username)
            user_filter = (
                settings.LDAP_USER_FILTER.format(
                    id_attribute=settings.LDAP_ID_ATTRIBUTE,
                    mail_attribute=settings.LDAP_MAIL_ATTRIBUTE,
                    input=escaped,
                )
                if settings.LDAP_USER_FILTER
                else ""
            )
            filter_text = (
                f"(&(|({settings.LDAP_ID_ATTRIBUTE}={escaped})({settings.LDAP_MAIL_ATTRIBUTE}={escaped})){user_filter})"
            )
            attrs = [settings.LDAP_ID_ATTRIBUTE, settings.LDAP_NAME_ATTRIBUTE, settings.LDAP_MAIL_ATTRIBUTE]
            matches = conn.search_s(settings.LDAP_BASE_DN, ldap.SCOPE_SUBTREE, filter_text, attrs)
            matches = [(dn, values) for dn, values in matches if dn]
            if len(matches) != 1:
                return None
            dn, values = matches[0]
            conn.simple_bind_s(dn, self.data.password)

            def decode(key: str) -> str | None:
                return values[key][0].decode("utf-8") if values.get(key) else None

            name = decode(settings.LDAP_ID_ATTRIBUTE)
            full_name = decode(settings.LDAP_NAME_ATTRIBUTE)
            email = decode(settings.LDAP_MAIL_ATTRIBUTE)
            if not name or not full_name or not email:
                return None
            is_admin = False
            if settings.LDAP_ADMIN_FILTER:
                try:
                    is_admin = bool(conn.search_s(dn, ldap.SCOPE_BASE, settings.LDAP_ADMIN_FILTER, []))
                except ldap.FILTER_ERROR, ldap.NO_SUCH_OBJECT:
                    logger.warning("Unable to determine LDAP admin status; defaulting to False")
            return {"username": name, "full_name": full_name, "email": email, "admin": is_admin}
        except ldap.INVALID_CREDENTIALS, ldap.NO_SUCH_OBJECT, ldap.FILTER_ERROR:
            return None
        finally:
            try:
                conn.unbind_s()
            except Exception:
                pass


class AsyncOpenIDProvider(AsyncAuthProvider):
    def __init__(self, data: UserInfo, use_default_groups: bool = False) -> None:
        super().__init__(data)
        self.use_default_groups = use_default_groups
        self.users = TortoiseUserRepository()

    @property
    def required_claims(self) -> set[str]:
        settings = get_app_settings()
        claims = {settings.OIDC_NAME_CLAIM, "email", settings.OIDC_USER_CLAIM}
        if settings.OIDC_REQUIRES_GROUP_CLAIM and not self.use_default_groups:
            claims.add(settings.OIDC_GROUPS_CLAIM)
        return claims

    async def authenticate(self) -> tuple[str, timedelta] | None:
        settings = get_app_settings()
        claims = self.data
        if not claims or not self.required_claims.issubset(claims.keys()):
            raise MissingClaimException()
        if any(not claims.get(claim) for claim in self.required_claims):
            raise MissingClaimException()
        if settings.OIDC_REQUIRES_EMAIL_VERIFICATION and not claims.get("email_verified", False):
            raise MissingClaimException()
        groups = claims.get(settings.OIDC_GROUPS_CLAIM, []) or []
        is_admin = settings.OIDC_ADMIN_GROUP in groups if settings.OIDC_ADMIN_GROUP else False
        is_valid_user = settings.OIDC_USER_GROUP in groups if settings.OIDC_USER_GROUP else True
        if settings.OIDC_REQUIRES_GROUP_CLAIM and not (is_valid_user or is_admin):
            return None
        user = await self.try_get_user(claims.get(settings.OIDC_USER_CLAIM))
        if user is None:
            if not settings.OIDC_SIGNUP_ENABLED:
                return None
            username = claims.get("preferred_username", claims.get("username", claims.get(settings.OIDC_USER_CLAIM)))
            user = await self.users.create(
                {
                    "username": username,
                    "password": "OIDC",
                    "full_name": claims.get(settings.OIDC_NAME_CLAIM),
                    "email": claims.get("email"),
                    "admin": is_admin,
                    "auth_method": AuthMethod.OIDC,
                    "group": settings.DEFAULT_GROUP,
                    "household": settings.DEFAULT_HOUSEHOLD,
                }
            )
        elif settings.OIDC_ADMIN_GROUP and user.admin != is_admin:
            user = await self.users.update(user.id, {"admin": is_admin}) or user
        await self._update_profile_image(user.id, claims)
        return self.access_token(user, settings.OIDC_REMEMBER_ME)

    async def _update_profile_image(self, user_id: Any, claims: UserInfo) -> None:
        from mealie.core.dependencies import get_temporary_path
        from mealie.core.security.providers.openid_provider import OpenIDProvider

        picture = claims.get("picture")
        if not isinstance(picture, str) or not picture:
            return
        helper = OpenIDProvider(None, claims)
        try:
            if not helper._is_safe_picture_scheme(picture):
                return
            user = await self.users.get_one(user_id)
            if user is None:
                return
            picture_hash = hashlib.sha256(picture.encode()).hexdigest()
            if user.external_avatar_hash == picture_hash:
                return
            content = await asyncio.to_thread(helper._fetch_picture, picture)
            with get_temporary_path() as temp_path:
                temp_image = Path(temp_path) / str(uuid4())
                temp_image.write_bytes(content)
                image = img.PillowMinifier.to_webp(temp_image)
                shutil.move(image, PrivateUser.get_directory(user_id) / "profile.webp")
            await self.users.update(user_id, {"cache_key": cache.new_key(), "external_avatar_hash": picture_hash})
        except Exception as error:
            logger.debug("[OIDC] Could not update profile image from picture claim: %s", error)


__all__ = ["AsyncAuthProvider", "AsyncCredentialsProvider", "AsyncLDAPProvider", "AsyncOpenIDProvider"]
