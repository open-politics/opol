"""Add meta_summary to Content

Revision ID: 06ed47c54696
Revises: 3b5e5778e4d7
Create Date: 2024-11-22 23:35:58.307253

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = '06ed47c54696'
down_revision = '3b5e5778e4d7'
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