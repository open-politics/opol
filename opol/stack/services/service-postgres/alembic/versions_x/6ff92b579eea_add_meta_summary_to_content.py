"""Add meta_summary to Content

Revision ID: 6ff92b579eea
Revises: 998ed7bdac7f
Create Date: 2024-11-23 01:31:31.673907

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '6ff92b579eea'
down_revision = '998ed7bdac7f'
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