"""Add meta_summary to Content

Revision ID: 4b807aab7df5
Revises: 2583708fc91e
Create Date: 2024-11-27 00:54:53.715803

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '4b807aab7df5'
down_revision = '2583708fc91e'
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