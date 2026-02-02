"""

Revision ID: aba94e302521
Revises:
Create Date: 2023-06-15 12:39:17.635318

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'aba94e302521'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            CREATE EXTENSION IF NOT EXISTS pgcrypto;
            CREATE OR REPLACE FUNCTION gen_nanoid(abbreviation varchar(5) default null)
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
              IF abbreviation is not null THEN
                id := abbreviation || '-' || id;
              END IF;
              RETURN id;
            END
            $$ LANGUAGE PLPGSQL STABLE;
            """
        )
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DROP FUNCTION IF EXISTS gen_nanoid;
            """
        )
    )
