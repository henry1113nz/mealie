from uuid import UUID

from fastapi import APIRouter
from slugify import slugify

from mealie.db.models.tortoise_models import Group, Household, Recipe, User
from mealie.schema.response import ValidationResponse

router = APIRouter()


@router.get("/user/name", response_model=ValidationResponse)
async def validate_user(name: str):
    """Checks if a user with the given name exists"""
    return ValidationResponse(valid=not await User.filter(username__iexact=name).exists())


@router.get("/user/email", response_model=ValidationResponse)
async def validate_user_email(email: str):
    """Checks if a user with the given name exists"""
    return ValidationResponse(valid=not await User.filter(email__iexact=email).exists())


@router.get("/group", response_model=ValidationResponse)
async def validate_group(name: str):
    """Checks if a group with the given name exists"""
    return ValidationResponse(valid=not await Group.filter(name=name).exists())


@router.get("/household", response_model=ValidationResponse)
async def validate_household(name: str):
    """Checks if a household with the given name exists"""
    return ValidationResponse(valid=not await Household.filter(name=name).exists())


@router.get("/recipe", response_model=ValidationResponse)
async def validate_recipe(group_id: UUID, name: str):
    """Checks if a recipe with the given slug exists"""
    slug = slugify(name)
    return ValidationResponse(valid=not await Recipe.filter(group_id=group_id, slug=slug).exists())
