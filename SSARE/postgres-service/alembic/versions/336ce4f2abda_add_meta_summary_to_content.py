"""Add meta_summary to Content

Revision ID: 336ce4f2abda
Revises: 73d7ce4823f4
Create Date: 2024-11-27 00:34:57.246532

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '336ce4f2abda'
down_revision = '73d7ce4823f4'
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