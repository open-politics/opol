"""Add meta_summary to Content

Revision ID: 20afcf07dd67
Revises: 3d217d9b2551
Create Date: 2024-11-26 22:00:45.163168

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '20afcf07dd67'
down_revision = '3d217d9b2551'
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