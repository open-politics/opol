"""Add meta_summary to Content

Revision ID: be803bc7a0ad
Revises: 1cfcaae58f7e
Create Date: 2024-11-18 17:54:28.294653

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = 'be803bc7a0ad'
down_revision = '1cfcaae58f7e'
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