"""Add meta_summary to Content

Revision ID: 6dcaa2caac12
Revises: 19df9d7fef4a
Create Date: 2024-11-27 02:36:09.208188

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '6dcaa2caac12'
down_revision = '19df9d7fef4a'
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