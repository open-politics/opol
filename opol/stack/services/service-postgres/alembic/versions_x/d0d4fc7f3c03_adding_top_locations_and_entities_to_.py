"""Adding top locations and entities to content

Revision ID: d0d4fc7f3c03
Revises: e975784ec160
Create Date: 2024-12-04 22:13:59.458494

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = 'd0d4fc7f3c03'
down_revision = 'e975784ec160'
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