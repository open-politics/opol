"""Add meta_summary to Content

Revision ID: 67ecec3bc62d
Revises: fd29893008bd
Create Date: 2024-11-23 01:03:54.735435

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '67ecec3bc62d'
down_revision = 'fd29893008bd'
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