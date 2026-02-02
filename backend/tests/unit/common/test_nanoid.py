import string

from src.common.nanoid import NanoId


def test_nanoid_length_without_abbrev():
    nano_id = NanoId.gen()
    assert len(nano_id) == NanoId._CHAR_SIZE


def test_nanoid_length_with_abbrev():
    abbrev = 'XYZ'
    nano_id = NanoId.gen(abbrev=abbrev)
    assert len(nano_id) == NanoId._CHAR_SIZE + len(abbrev) + 1  # +1 for the hyphen


def test_nanoid_starts_with_abbrev():
    abbrev = 'XYZ'
    nano_id = NanoId.gen(abbrev=abbrev)
    assert nano_id.startswith(f'{abbrev}-')


def test_nanoid_chars_in_pool_without_abbrev():
    char_pool = set(string.digits + string.ascii_letters)
    nano_id = NanoId.gen()
    for char in nano_id:
        assert char in char_pool


def test_nanoid_chars_in_pool_with_abbrev():
    char_pool = set(string.digits + string.ascii_letters)
    abbrev = 'XYZ'
    nano_id = NanoId.gen(abbrev=abbrev)
    nano_id_without_abbrev = nano_id.split('-')[1]
    for char in nano_id_without_abbrev:
        assert char in char_pool
