"""Add meta_summary to Content

Revision ID: 367e8ab63418
Revises: d5ac026c5693
Create Date: 2024-11-27 04:20:22.754268

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '367e8ab63418'
down_revision = 'd5ac026c5693'
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