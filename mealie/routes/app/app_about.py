from fastapi import APIRouter, Response

from mealie.core.config import get_app_settings
from mealie.core.settings.static import APP_VERSION
from mealie.db.models.tortoise_models import Group, GroupPreferencesModel, Household, HouseholdPreferencesModel, User
from mealie.schema.admin.about import AppInfo, AppStartupInfo, AppTheme

router = APIRouter(prefix="/about")


@router.get("", response_model=AppInfo)
async def get_app_info():
    """Get general application information"""
    settings = get_app_settings()

    default_group_slug: str | None = None
    default_household_slug: str | None = None

    default_group = await Group.filter(name=settings.DEFAULT_GROUP).first()
    if default_group:
        group_preferences = await GroupPreferencesModel.filter(group_id=default_group.id).first()
        if group_preferences and not group_preferences.private_group:
            default_group_slug = default_group.slug

    if default_group and default_group_slug:
        default_household = await Household.filter(group_id=default_group.id, name=settings.DEFAULT_HOUSEHOLD).first()
        if default_household:
            household_preferences = await HouseholdPreferencesModel.filter(household_id=default_household.id).first()
            if household_preferences and not household_preferences.private_household:
                default_household_slug = default_household.slug

    return AppInfo(
        version=APP_VERSION,
        demo_status=settings.IS_DEMO,
        production=settings.PRODUCTION,
        allow_signup=settings.ALLOW_SIGNUP,
        default_group_slug=default_group_slug,
        default_household_slug=default_household_slug,
        enable_oidc=settings.OIDC_READY,
        oidc_redirect=settings.OIDC_AUTO_REDIRECT,
        oidc_provider_name=settings.OIDC_PROVIDER_NAME,
        allow_password_login=settings.ALLOW_PASSWORD_LOGIN,
        token_time=settings.TOKEN_TIME,
        allowed_iframe_hosts=settings.allowed_iframe_hosts,
    )


@router.get("/startup-info", response_model=AppStartupInfo)
async def get_startup_info():
    """returns helpful startup information"""
    settings = get_app_settings()

    is_first_login = await User.filter(email=settings._DEFAULT_EMAIL).exists()

    return AppStartupInfo(
        is_first_login=is_first_login,
        is_demo=settings.IS_DEMO,
    )


@router.get("/theme", response_model=AppTheme)
def get_app_theme(resp: Response):
    """Get's the current theme settings"""
    settings = get_app_settings()

    resp.headers["Cache-Control"] = "public, max-age=604800"
    return AppTheme(**settings.theme.model_dump())
