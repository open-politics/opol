"""Rename thematic_locations to top_locations in ContentEvaluation

Revision ID: c4c3c69a4a4b
Revises: 400604920812
Create Date: 2025-03-13 23:23:16.176451

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = 'c4c3c69a4a4b'
down_revision = '400604920812'
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