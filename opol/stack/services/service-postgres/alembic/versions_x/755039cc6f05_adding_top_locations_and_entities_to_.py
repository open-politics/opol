"""Adding top locations and entities to content

Revision ID: 755039cc6f05
Revises: ea93e1fa0b6d
Create Date: 2024-12-04 20:28:38.333206

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '755039cc6f05'
down_revision = 'ea93e1fa0b6d'
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