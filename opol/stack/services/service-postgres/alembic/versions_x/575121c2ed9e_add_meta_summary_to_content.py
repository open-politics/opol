"""Add meta_summary to Content

Revision ID: 575121c2ed9e
Revises: 6436682a3f36
Create Date: 2024-11-27 02:52:39.463999

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '575121c2ed9e'
down_revision = '6436682a3f36'
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