"""Add meta_summary to Content

Revision ID: eef25b2f3ebd
Revises: 758b0a191aa7
Create Date: 2024-11-26 20:26:30.801508

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = 'eef25b2f3ebd'
down_revision = '758b0a191aa7'
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