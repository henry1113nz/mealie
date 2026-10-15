from fastapi import APIRouter, Depends, HTTPException, status

from mealie.core.config import get_app_settings
from mealie.db.tortoise_setup import require_tortoise_ready
from mealie.routes._base import BasePublicController, controller
from mealie.schema.response import ErrorResponse
from mealie.schema.user.registration import CreateUserRegistration
from mealie.schema.user.user import UserOut
from mealie.services.event_bus_service.event_bus_service import EventBusService
from mealie.services.event_bus_service.event_types import EventTypes, EventUserSignupData
from mealie.services.user_services.tortoise_registration_service import TortoiseRegistrationService

router = APIRouter(prefix="/register")


@controller(router)
class RegistrationController(BasePublicController):
    event_bus: EventBusService = Depends(EventBusService.as_dependency)

    @router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
    async def register_new_user(self, data: CreateUserRegistration, _tortoise_ready=Depends(require_tortoise_ready)):
        settings = get_app_settings()

        if not settings.ALLOW_SIGNUP and data.group_token is None or data.group_token == "":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorResponse.respond("User Registration is Disabled"),
            )

        registration_service = TortoiseRegistrationService(self.translator)

        result = await registration_service.register_user(data)

        self.event_bus.dispatch(
            integration_id="registration",
            group_id=result.group_id,
            household_id=result.household_id,
            event_type=EventTypes.user_signup,
            document_data=EventUserSignupData(username=result.username, email=result.email),
        )

        return result
