import json

from sqlalchemy.types import JSON, TypeDecorator


class SuperJSON(TypeDecorator):
    """
    Handles Decimal and Datetime objects natively - no need for conversions
    """

    impl = JSON

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.loads(json.dumps(value, default=str))
        return value
