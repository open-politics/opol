"""Add meta_summary to Content

Revision ID: 3190ffc3c97d
Revises: 336ce4f2abda
Create Date: 2024-11-27 00:39:32.170093

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '3190ffc3c97d'
down_revision = '336ce4f2abda'
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