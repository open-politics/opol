"""Add meta_summary to Content

Revision ID: 7d7db9c4e89f
Revises: 0ce94a033558
Create Date: 2024-11-18 13:33:16.181642

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '7d7db9c4e89f'
down_revision = '0ce94a033558'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###