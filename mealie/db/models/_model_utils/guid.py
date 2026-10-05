from uuid import UUID, uuid4


class GUID(UUID):
    """UUID value helper retained for import and export payloads."""

    @staticmethod
    def generate() -> UUID:
        return uuid4()

    @staticmethod
    def convert_value_to_guid(value: UUID | str | None, dialect=None) -> str | None:
        if value is None:
            return None
        return str(value)
