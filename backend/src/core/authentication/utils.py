import base64
import hashlib
import secrets


def generate_mfa_code(length=6):
    range_start = 10 ** (length - 1)
    range_end = 10**length - 1
    code = secrets.randbelow(range_end - range_start + 1) + range_start
    return str(code)


def create_derived_key(existing_key: str):
    hasher = hashlib.sha256()
    hasher.update(existing_key.encode('utf-8'))
    hash_digest = hasher.digest()
    b64_encoded = base64.urlsafe_b64encode(hash_digest).decode('utf-8')
    length = len(existing_key)
    truncated_key = b64_encoded[:length]
    return truncated_key
