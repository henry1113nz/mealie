from pydantic import UUID4, ConfigDict

from mealie.schema._mealie import MealieModel

from .user import PrivateUser


class ForgotPassword(MealieModel):
    email: str


class PasswordResetToken(MealieModel):
    token: str


class ValidateResetToken(MealieModel):
    token: str


class ResetPassword(ValidateResetToken):
    email: str
    password: str
    passwordConfirm: str


class SavePasswordResetToken(MealieModel):
    user_id: UUID4
    token: str


class PrivatePasswordResetToken(SavePasswordResetToken):
    user: PrivateUser
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def loader_options(cls) -> list[str]:
        return ["user__group", "user__household", "user__tokens"]
