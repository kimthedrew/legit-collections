"""Updated price field type

Revision ID: 398999a13177
Revises: c8491f2a5359
Create Date: 2025-06-20 14:29:12.090137

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '398999a13177'
down_revision = 'c8491f2a5359'
branch_labels = None
depends_on = None


def upgrade():
    # First, add the column as nullable
    op.add_column('shoes', sa.Column('price', sa.Float(), nullable=True))
    
    # Set default value for existing rows
    op.execute("UPDATE shoes SET price = 0.0 WHERE price IS NULL")
    
    # Now change to NOT NULL
    op.alter_column('shoes', 'price', nullable=False)
    # ### end Alembic commands ###


def downgrade():
    op.drop_column('shoes', 'price')
    # ### end Alembic commands ###
