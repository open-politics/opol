"""Initial migration

Revision ID: be81e1f0d6a8
Revises: 9395c7d0434b
Create Date: 2025-03-24 01:18:26.176695

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = 'be81e1f0d6a8'
down_revision = '9395c7d0434b'
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