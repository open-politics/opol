"""Adding top locations and entities to content

Revision ID: ecf4576cd00e
Revises: 5ed738650464
Create Date: 2024-12-04 22:06:16.759520

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector



# revision identifiers, used by Alembic.
revision = 'ecf4576cd00e'
down_revision = '5ed738650464'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('topcontententity',
    sa.Column('content_id', sa.Uuid(), nullable=False),
    sa.Column('entity_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['content_id'], ['content.id'], ),
    sa.ForeignKeyConstraint(['entity_id'], ['entity.id'], ),
    sa.PrimaryKeyConstraint('content_id', 'entity_id')
    )
    op.create_table('topcontentlocation',
    sa.Column('content_id', sa.Uuid(), nullable=False),
    sa.Column('location_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['content_id'], ['content.id'], ),
    sa.ForeignKeyConstraint(['location_id'], ['location.id'], ),
    sa.PrimaryKeyConstraint('content_id', 'location_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('topcontentlocation')
    op.drop_table('topcontententity')
    # ### end Alembic commands ###