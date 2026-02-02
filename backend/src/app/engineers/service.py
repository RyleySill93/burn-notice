from src.app.engineers.domains import EngineerCreate, EngineerRead
from src.app.engineers.models import Engineer


class EngineerService:
    @staticmethod
    def get_or_create(customer_id: str, external_id: str, display_name: str) -> EngineerRead:
        """Get an engineer by external_id within a customer, or create if doesn't exist."""
        existing = Engineer.get_or_none(customer_id=customer_id, external_id=external_id)
        if existing:
            # Update display name if changed
            if existing.display_name != display_name:
                Engineer.update(existing.id, display_name=display_name)
                return Engineer.get(id=existing.id)
            return existing

        return Engineer.create(
            EngineerCreate(customer_id=customer_id, external_id=external_id, display_name=display_name)
        )

    @staticmethod
    def list_by_customer(customer_id: str) -> list[EngineerRead]:
        """List all engineers for a customer/team."""
        return Engineer.list(customer_id=customer_id)

    @staticmethod
    def get_by_external_id(customer_id: str, external_id: str) -> EngineerRead | None:
        """Get an engineer by their external ID within a customer."""
        return Engineer.get_or_none(customer_id=customer_id, external_id=external_id)
