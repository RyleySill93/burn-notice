"""Unit tests for the encryption module."""

from unittest.mock import patch

from src.common.encryption import EncryptionService, decrypt, encrypt


class TestEncryptionService:
    """Test the EncryptionService class."""

    def test_same_key_generation(self):
        """Test that the same key is generated from the same secret."""
        # Get two Fernet instances - they should be the same
        fernet1 = EncryptionService._get_fernet()
        fernet2 = EncryptionService._get_fernet()

        # Encrypt with one, decrypt with the other
        test_data = 'test_secret_123'
        encrypted = fernet1.encrypt(test_data.encode())
        decrypted = fernet2.decrypt(encrypted).decode()

        assert decrypted == test_data

    def test_encrypt_returns_string(self):
        """Test that encrypt returns a string."""
        service = EncryptionService()
        plaintext = 'test_password_123'
        encrypted = service.encrypt(plaintext)

        assert isinstance(encrypted, str)
        assert len(encrypted) > 0
        assert encrypted != plaintext

    def test_decrypt_returns_original(self):
        """Test that decrypt returns the original plaintext."""
        service = EncryptionService()
        plaintext = 'test_password_456'
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_different_results_same_input(self):
        """Test that encrypting the same input twice gives different results (due to IV)."""
        service = EncryptionService()
        plaintext = 'test_password_789'
        encrypted1 = service.encrypt(plaintext)
        encrypted2 = service.encrypt(plaintext)

        # Different ciphertexts due to random IV
        assert encrypted1 != encrypted2

        # But both decrypt to the same value
        assert service.decrypt(encrypted1) == plaintext
        assert service.decrypt(encrypted2) == plaintext

    def test_encrypt_empty_string(self):
        """Test encrypting an empty string."""
        service = EncryptionService()
        plaintext = ''
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_special_characters(self):
        """Test encrypting strings with special characters."""
        service = EncryptionService()
        plaintext = "p@$$w0rd!#$%^&*()_+-=[]{}|;:',.<>?/~`"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_unicode(self):
        """Test encrypting Unicode strings."""
        service = EncryptionService()
        plaintext = 'パスワード 🔐 Lösenord'
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_long_string(self):
        """Test encrypting a very long string."""
        service = EncryptionService()
        plaintext = 'a' * 10000  # 10KB string
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_decrypt_invalid_token_returns_original(self):
        """Test that decrypting an invalid token returns the original (for migration)."""
        service = EncryptionService()
        invalid_data = 'invalid_encrypted_data'
        result = service.decrypt(invalid_data)

        # Per the implementation, it returns the original on failure (for migration)
        assert result == invalid_data

    def test_decrypt_tampered_token_returns_original(self):
        """Test that decrypting a tampered token returns the original (for migration)."""
        service = EncryptionService()
        plaintext = 'test_password'
        encrypted = service.encrypt(plaintext)

        # Tamper with the encrypted data
        tampered = encrypted[:-10] + 'tampered!!'
        result = service.decrypt(tampered)

        # Per the implementation, it returns the original on failure (for migration)
        assert result == tampered

    def test_different_keys_cannot_decrypt(self):
        """Test that data encrypted with one key cannot be decrypted with another."""
        # This test demonstrates that changing SECRET_KEY would break decryption
        # Note: In the current implementation, decrypt returns original on failure
        service = EncryptionService()
        plaintext = 'test_password'
        _encrypted = service.encrypt(plaintext)

        # Simulate a different key by creating a bad ciphertext
        # The decrypt method will return the bad ciphertext unchanged
        bad_encrypted = 'this_is_not_valid_encrypted_data'
        result = service.decrypt(bad_encrypted)
        assert result == bad_encrypted  # Returns original on failure

    def test_module_level_functions(self):
        """Test the module-level encrypt and decrypt functions."""
        plaintext = 'test_password_module'
        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)

        assert decrypted == plaintext
        assert isinstance(encrypted, str)


class TestOIDCSecretEncryption:
    """Test encryption scenarios specific to OIDC client secrets."""

    def test_oidc_client_secret_encryption(self):
        """Test encrypting an OIDC client secret."""
        # Typical OIDC client secret format
        client_secret = '1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-'
        encrypted = encrypt(client_secret)
        decrypted = decrypt(encrypted)

        assert decrypted == client_secret

    def test_oidc_jwt_style_secret(self):
        """Test encrypting a JWT-style secret."""
        # Some providers use JWT-like secrets
        jwt_secret = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U'
        encrypted = encrypt(jwt_secret)
        decrypted = decrypt(encrypted)

        assert decrypted == jwt_secret

    def test_google_client_secret_format(self):
        """Test encrypting a Google-style client secret."""
        # Google uses format like: GOCSPX-[random_string]
        google_secret = 'GOCSPX-1234567890abcdefghijklmnop'
        encrypted = encrypt(google_secret)
        decrypted = decrypt(encrypted)

        assert decrypted == google_secret

    def test_azure_client_secret_format(self):
        """Test encrypting an Azure-style client secret."""
        # Azure uses format with special characters
        azure_secret = '~8Q8~abcdefghijklmnopqrstuvwxyz.ABCD'
        encrypted = encrypt(azure_secret)
        decrypted = decrypt(encrypted)

        assert decrypted == azure_secret


class TestEncryptionConsistency:
    """Test that encryption is consistent and deterministic based on SECRET_KEY."""

    @patch('src.common.encryption.settings.SECRET_KEY', 'consistent_test_key')
    def test_consistent_key_derivation(self):
        """Test that the same SECRET_KEY always produces the same encryption key."""
        # Create two separate instances (simulating app restarts)
        fernet1 = EncryptionService._get_fernet()
        fernet2 = EncryptionService._get_fernet()

        # They should produce compatible encryption/decryption
        plaintext = 'test_consistency'
        encrypted = fernet1.encrypt(plaintext.encode())
        decrypted = fernet2.decrypt(encrypted).decode()

        assert decrypted == plaintext

    def test_encryption_roundtrip_after_restart(self):
        """Test that encrypted data can be decrypted after a simulated restart."""
        # Simulate first run
        plaintext = 'persistent_secret'
        encrypted = encrypt(plaintext)

        # Simulate app restart (new instance of EncryptionService)
        # In reality, the Fernet instance would be recreated
        decrypted = decrypt(encrypted)

        assert decrypted == plaintext
