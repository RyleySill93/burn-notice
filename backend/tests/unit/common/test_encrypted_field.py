"""Unit tests for the SQLAlchemy EncryptedString field type."""

import pytest
from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import Session, declarative_base

from src.common.encrypted_field import EncryptedString, EncryptedText

# Create a test model
Base = declarative_base()


class TestModel(Base):
    __tablename__ = 'test_encrypted_model'

    id = Column(Integer, primary_key=True)
    public_data = Column(String)  # Regular field
    secret_data = Column(EncryptedString)  # Encrypted field
    large_secret = Column(EncryptedText())  # Large encrypted field


class TestEncryptedStringField:
    """Test the EncryptedString SQLAlchemy field type."""

    @pytest.fixture
    def db_session(self):
        """Create an in-memory SQLite database for testing."""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        session = Session(engine)
        yield session
        session.close()

    def test_transparent_encryption_decryption(self, db_session):
        """Test that values are transparently encrypted and decrypted."""
        # Create a record with secret data
        model = TestModel(public_data='This is public', secret_data='This is secret!')
        db_session.add(model)
        db_session.commit()

        # Retrieve the record
        retrieved = db_session.query(TestModel).first()

        # The secret should be decrypted automatically
        assert retrieved.secret_data == 'This is secret!'
        assert retrieved.public_data == 'This is public'

    def test_actual_encryption_in_database(self, db_session):
        """Test that the value is actually encrypted in the database."""
        secret_value = 'my-secret-password-123'

        # Create a record
        model = TestModel(secret_data=secret_value)
        db_session.add(model)
        db_session.commit()
        record_id = model.id

        # Query raw value from database
        raw_result = db_session.execute(
            text(f'SELECT secret_data FROM test_encrypted_model WHERE id = {record_id}')
        ).first()

        raw_value = raw_result[0]

        # The raw value should be encrypted (starts with Fernet prefix)
        assert raw_value != secret_value
        assert raw_value.startswith('gAAAAA')  # Fernet token prefix

        # But accessing via ORM should give decrypted value
        model = db_session.query(TestModel).filter_by(id=record_id).first()
        assert model.secret_data == secret_value

    def test_null_values(self, db_session):
        """Test that NULL values are handled correctly."""
        model = TestModel(public_data='Public', secret_data=None)
        db_session.add(model)
        db_session.commit()

        retrieved = db_session.query(TestModel).first()
        assert retrieved.secret_data is None

    def test_empty_string(self, db_session):
        """Test that empty strings are handled correctly."""
        model = TestModel(secret_data='')
        db_session.add(model)
        db_session.commit()

        retrieved = db_session.query(TestModel).first()
        assert retrieved.secret_data == ''

    def test_update_encrypted_field(self, db_session):
        """Test updating an encrypted field."""
        # Create initial record
        model = TestModel(secret_data='initial_secret')
        db_session.add(model)
        db_session.commit()
        record_id = model.id

        # Update the secret
        model = db_session.query(TestModel).filter_by(id=record_id).first()
        model.secret_data = 'updated_secret'
        db_session.commit()

        # Verify the update
        model = db_session.query(TestModel).filter_by(id=record_id).first()
        assert model.secret_data == 'updated_secret'

    def test_special_characters_in_encrypted_field(self, db_session):
        """Test that special characters are handled correctly."""
        special_secret = "p@$$w0rd!#$%^&*()_+-=[]{}|;:',.<>?/~`"

        model = TestModel(secret_data=special_secret)
        db_session.add(model)
        db_session.commit()

        retrieved = db_session.query(TestModel).first()
        assert retrieved.secret_data == special_secret

    def test_unicode_in_encrypted_field(self, db_session):
        """Test that Unicode is handled correctly."""
        unicode_secret = 'パスワード 🔐 Lösenord'

        model = TestModel(secret_data=unicode_secret)
        db_session.add(model)
        db_session.commit()

        retrieved = db_session.query(TestModel).first()
        assert retrieved.secret_data == unicode_secret

    def test_already_encrypted_value_migration(self, db_session):
        """Test that already encrypted values (migration scenario) are handled."""
        # Simulate a value that's already encrypted (starts with gAAAAA)
        already_encrypted = 'gAAAAABh3K4Rc5_fake_encrypted_value'

        model = TestModel(secret_data=already_encrypted)
        db_session.add(model)
        db_session.commit()

        # The field should detect it's already encrypted and not double-encrypt
        retrieved = db_session.query(TestModel).first()
        # It will try to decrypt and fail, returning the original
        assert retrieved.secret_data == already_encrypted

    def test_encrypted_text_field(self, db_session):
        """Test the EncryptedText field for large values."""
        large_secret = 'secret_data_' * 1000  # ~12KB of text

        model = TestModel(large_secret=large_secret)
        db_session.add(model)
        db_session.commit()

        retrieved = db_session.query(TestModel).first()
        assert retrieved.large_secret == large_secret
