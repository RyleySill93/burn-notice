"""SQLAlchemy custom type for transparent encryption/decryption of sensitive fields."""

from typing import Optional

from sqlalchemy import String, TypeDecorator
from sqlalchemy.engine import Dialect

from src.common.encryption import decrypt, encrypt


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy type that transparently encrypts/decrypts string values.

    Usage:
        class MyModel(Base):
            __tablename__ = 'my_table'

            id = Column(Integer, primary_key=True)
            # Regular string field
            public_data = Column(String)
            # Encrypted string field - automatically encrypted on save, decrypted on load
            secret_data = Column(EncryptedString)

    The encryption happens transparently:
        # When you set it:
        model.secret_data = "my-secret-key"  # Stored encrypted in DB

        # When you read it:
        print(model.secret_data)  # Automatically decrypted to "my-secret-key"
    """

    impl = String
    cache_ok = True  # This type is safe for caching

    def process_bind_param(self, value: Optional[str], dialect: Dialect) -> Optional[str]:
        """
        Encrypt the value before storing in the database.

        Called when:
        - Creating a new record
        - Updating an existing record
        - Using the value in a query parameter
        """
        if value is None:
            return None

        # Skip encryption if already encrypted (migration support)
        # Encrypted values start with 'gAAAAA' (Fernet token prefix)
        if isinstance(value, str) and value.startswith('gAAAAA'):
            return value

        return encrypt(value)

    def process_result_value(self, value: Optional[str], dialect: Dialect) -> Optional[str]:
        """
        Decrypt the value when loading from the database.

        Called when:
        - Loading a record from the database
        - Accessing the field value
        """
        if value is None:
            return None

        return decrypt(value)

    def process_literal_param(self, value: Optional[str], dialect: Dialect) -> str:
        """
        Handle literal SQL compilation (rarely used, mainly for debugging).
        """
        if value is None:
            return 'NULL'
        return f"'{encrypt(value)}'"

    @property
    def python_type(self):
        """The Python type of values handled by this type decorator."""
        return str


class EncryptedText(EncryptedString):
    """
    Variant for larger text fields that need encryption.

    Same as EncryptedString but uses TEXT column type for larger values.
    """

    impl = String  # SQLAlchemy will use TEXT for unlimited length

    def __init__(self, length=None):
        """
        Initialize with optional length limit.

        Args:
            length: Maximum length (None for unlimited TEXT field)
        """
        super().__init__()
        if length:
            self.impl = String(length)
