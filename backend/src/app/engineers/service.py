from src.app.engineers.domains import EngineerCreate, EngineerRead
from src.app.engineers.models import Engineer


class EngineerService:
    @staticmethod
    def get_or_create(external_id: str, display_name: str) -> EngineerRead:
        """Get an engineer by external_id, or create if doesn't exist."""
        existing = Engineer.get_or_none(external_id=external_id)
        if existing:
            # Update display name if changed
            if existing.display_name != display_name:
                Engineer.update(existing.id, display_name=display_name)
                return Engineer.get(id=existing.id)
            return existing

        return Engineer.create(EngineerCreate(external_id=external_id, display_name=display_name))

    @staticmethod
    def list_all() -> list[EngineerRead]:
        """List all engineers."""
        return Engineer.list()

    @staticmethod
    def get_by_external_id(external_id: str) -> EngineerRead | None:
        """Get an engineer by their external ID."""
        return Engineer.get_or_none(external_id=external_id)
