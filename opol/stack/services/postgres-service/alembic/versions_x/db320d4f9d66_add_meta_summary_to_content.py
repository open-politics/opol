"""Add meta_summary to Content

Revision ID: db320d4f9d66
Revises: 6dcaa2caac12
Create Date: 2024-11-27 02:37:47.962062

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = 'db320d4f9d66'
down_revision = '6dcaa2caac12'
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