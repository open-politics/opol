"""Add meta_summary to Content

Revision ID: 3ccdf90706bf
Revises: 3a7c15c6a24d
Create Date: 2024-11-23 00:57:24.867178

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '3ccdf90706bf'
down_revision = '3a7c15c6a24d'
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