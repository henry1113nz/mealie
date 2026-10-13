from datetime import UTC, datetime

from pydantic import UUID4

from mealie.db.models.tortoise_models import Group, Household
from mealie.schema.household.webhook import ReadWebhook
from mealie.services.event_bus_service.event_bus_listeners import WebhookEventListener
from mealie.services.event_bus_service.event_bus_service import EventBusService
from mealie.services.event_bus_service.event_types import (
    INTERNAL_INTEGRATION_ID,
    Event,
    EventBusMessage,
    EventDocumentType,
    EventOperation,
    EventTypes,
    EventWebhookData,
)

last_ran = datetime.now(UTC)


async def post_group_webhooks(
    start_dt: datetime | None = None, group_id: UUID4 | None = None, household_id: UUID4 | None = None
) -> None:
    """Post webhook events to specified group, or all groups"""

    global last_ran

    # if not specified, start the query at the last time the service ran
    start_dt = start_dt or last_ran

    # end the query at the current time
    last_ran = end_dt = datetime.now(UTC)

    if group_id is None:
        # publish the webhook event to each group's event bus
        group_ids = await Group.all().values_list("id", flat=True)

    else:
        group_ids = [group_id]

    """
    At this time only mealplan webhooks are supported. To add support for more types,
    add a dispatch event for that type here (e.g. EventDocumentType.recipe_bulk_report) and
    handle the webhook data in the webhook event bus listener
    """

    event_type = EventTypes.webhook_task
    event_document_data = EventWebhookData(
        document_type=EventDocumentType.mealplan,
        operation=EventOperation.info,
        webhook_start_dt=start_dt,
        webhook_end_dt=end_dt,
    )

    for group_id in group_ids:
        if household_id is None:
            household_ids = await Household.filter(group_id=group_id).values_list("id", flat=True)
        else:
            household_ids = [household_id]

        for household_id in household_ids:
            event_bus = EventBusService()
            event_bus.dispatch(
                integration_id=INTERNAL_INTEGRATION_ID,
                group_id=group_id,
                household_id=household_id,
                event_type=event_type,
                document_data=event_document_data,
            )


def post_test_webhook(webhook: ReadWebhook, message: str = "") -> None:
    dt = datetime.min.replace(tzinfo=UTC)
    event_type = EventTypes.test_message

    event_document_data = EventWebhookData(
        document_type=EventDocumentType.generic,
        operation=EventOperation.info,
        webhook_start_dt=dt,
        webhook_end_dt=dt,
    )
    event = Event(
        message=EventBusMessage.from_type(event_type, body=message),
        event_type=event_type,
        integration_id=INTERNAL_INTEGRATION_ID,
        document_data=event_document_data,
    )

    listener = WebhookEventListener(webhook.group_id, webhook.household_id)
    listener.publish_to_subscribers(event, [webhook])
