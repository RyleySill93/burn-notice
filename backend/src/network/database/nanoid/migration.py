"""empty message

Revision ID: 3971568258a7
Revises:
Create Date: 2023-02-20 20:53:16.393145

"""

from alembic import op
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '3971568258a7'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            CREATE EXTENSION IF NOT EXISTS pgcrypto;

            CREATE OR REPLACE FUNCTION gen_nanoid()
            RETURNS text AS $$
            DECLARE
              id text := '';
              id_size int := 13;
              i int := 0;
              char_pool char(64) := '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';
              bytes bytea := gen_random_bytes(id_size);
              byte int;
              pos int;
            BEGIN
              WHILE i < id_size LOOP
                byte := get_byte(bytes, i);
                pos := (byte & 63) + 1; -- + 1 substr starts at 1
                id := id || substr(char_pool, pos, 1);
                i = i + 1;
              END LOOP;
              RETURN id;
            END
            $$ LANGUAGE PLPGSQL STABLE;
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text("""
            DROP FUNCTION IF EXISTS gen_nanoid;
            """)
    )
