"""Add meta_summary to Content

Revision ID: 3a7c15c6a24d
Revises: 09674f57d687
Create Date: 2024-11-23 00:56:11.506821

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '3a7c15c6a24d'
down_revision = '09674f57d687'
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