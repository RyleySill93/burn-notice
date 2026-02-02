import string
from math import ceil, log
from os import urandom
from typing import TypeAlias

# Create a NanoId type which is used for primary keys
# We can add more specific typing for this in the future.
# Examples: prop-XSqS5h9vFTSgP, cltr-yb6GG995oiBf, rptr-kwA4kDkqoS8V7
NanoIdType: TypeAlias = str


def generate_custom_nanoid(size: int = 8, char_pool: str | None = None) -> NanoIdType:
    """
    Generate a short random url safe id great for public links / urls
    Entropy here -> https://zelark.github.io/nano-id-cc/
    """

    def gen_bytes(size: int) -> bytearray:
        return bytearray(urandom(size))

    if char_pool is None:
        char_pool = string.digits + string.ascii_letters

    char_pool_len = len(char_pool)
    mask = 1
    if char_pool_len > 1:
        mask = (2 << int(log(char_pool_len - 1) / log(2))) - 1
    step = int(ceil(1.6 * mask * size / char_pool_len))

    id = ''
    # Ensure bits generated fit in specified character pool
    while True:
        random_bytes = gen_bytes(step)
        for i in range(step):
            random_byte = random_bytes[i] & mask
            if random_byte < char_pool_len:
                if char_pool[random_byte]:
                    id += char_pool[random_byte]

                    if len(id) == size:
                        return id


class NanoId:
    """
    ID used as primary key
    """

    _CHAR_SIZE = 13

    @classmethod
    def gen(cls, abbrev: str | None = None) -> NanoIdType:
        char_pool = string.digits + string.ascii_letters
        nano_id = generate_custom_nanoid(size=cls._CHAR_SIZE, char_pool=char_pool)
        if abbrev:
            nano_id = f'{abbrev}-{nano_id}'

        return nano_id
