"""Initial migration

Revision ID: c9399d4ec65e
Revises: 
Create Date: 2024-11-10 21:11:37.607422

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import pgvector  
from pgvector.sqlalchemy import Vector

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c9399d4ec65e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('classificationdimension',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('type', sa.Enum('STRING', 'INTEGER', 'LIST_STRING', 'FLOAT', 'BOOLEAN', name='classificationtype'), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_classificationdimension_name'), 'classificationdimension', ['name'], unique=True)
    op.create_index(op.f('ix_classificationdimension_type'), 'classificationdimension', ['type'], unique=False)
    op.create_table('content',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('url', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('content_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('source', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('insertion_date', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('content_language', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('author', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('publication_date', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('text_content', sa.Text(), nullable=True),
    sa.Column('embeddings', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_content_author'), 'content', ['author'], unique=False)
    op.create_index(op.f('ix_content_content_language'), 'content', ['content_language'], unique=False)
    op.create_index(op.f('ix_content_insertion_date'), 'content', ['insertion_date'], unique=False)
    op.create_index(op.f('ix_content_publication_date'), 'content', ['publication_date'], unique=False)
    op.create_index(op.f('ix_content_source'), 'content', ['source'], unique=False)
    op.create_index(op.f('ix_content_title'), 'content', ['title'], unique=False)
    op.create_index(op.f('ix_content_url'), 'content', ['url'], unique=True)
    op.create_table('entity',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('entity_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_entity_entity_type'), 'entity', ['entity_type'], unique=False)
    op.create_index(op.f('ix_entity_name'), 'entity', ['name'], unique=False)
    op.create_table('location',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('location_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('coordinates', pgvector.sqlalchemy.vector.VECTOR(dim=2), nullable=True),
    sa.Column('weight', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_location_location_type'), 'location', ['location_type'], unique=False)
    op.create_index(op.f('ix_location_name'), 'location', ['name'], unique=False)
    op.create_table('tag',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tag_name'), 'tag', ['name'], unique=True)
    op.create_table('topic',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('keywords', sa.ARRAY(sa.Text()), nullable=True),
    sa.Column('top_entities', sa.ARRAY(sa.Text()), nullable=True),
    sa.Column('geo_reach', sa.ARRAY(sa.Text()), nullable=True),
    sa.Column('content_count', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_topic_content_count'), 'topic', ['content_count'], unique=False)
    op.create_index(op.f('ix_topic_name'), 'topic', ['name'], unique=False)
    op.create_table('contentchunk',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('content_id', sa.Uuid(), nullable=False),
    sa.Column('chunk_number', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=True),
    sa.Column('embeddings', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
    sa.ForeignKeyConstraint(['content_id'], ['content.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contentchunk_chunk_number'), 'contentchunk', ['chunk_number'], unique=False)
    op.create_index(op.f('ix_contentchunk_content_id'), 'contentchunk', ['content_id'], unique=False)
    op.create_table('contententity',
    sa.Column('content_id', sa.Uuid(), nullable=False),
    sa.Column('entity_id', sa.Uuid(), nullable=False),
    sa.Column('frequency', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['content_id'], ['content.id'], ),
    sa.ForeignKeyConstraint(['entity_id'], ['entity.id'], ),
    sa.PrimaryKeyConstraint('content_id', 'entity_id')
    )
    op.create_table('contentevaluation',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('content_id', sa.Uuid(), nullable=False),
    sa.Column('rhetoric', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('sociocultural_interest', sa.Integer(), nullable=True),
    sa.Column('global_political_impact', sa.Integer(), nullable=True),
    sa.Column('regional_political_impact', sa.Integer(), nullable=True),
    sa.Column('global_economic_impact', sa.Integer(), nullable=True),
    sa.Column('regional_economic_impact', sa.Integer(), nullable=True),
    sa.Column('event_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('event_subtype', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('keywords', sa.ARRAY(sa.Text()), nullable=True),
    sa.Column('categories', sa.ARRAY(sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['content_id'], ['content.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contentevaluation_rhetoric'), 'contentevaluation', ['rhetoric'], unique=False)
    op.create_table('contenttag',
    sa.Column('content_id', sa.Uuid(), nullable=False),
    sa.Column('tag_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['content_id'], ['content.id'], ),
    sa.ForeignKeyConstraint(['tag_id'], ['tag.id'], ),
    sa.PrimaryKeyConstraint('content_id', 'tag_id')
    )
    op.create_table('contenttopic',
    sa.Column('content_id', sa.Uuid(), nullable=False),
    sa.Column('topic_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['content_id'], ['content.id'], ),
    sa.ForeignKeyConstraint(['topic_id'], ['topic.id'], ),
    sa.PrimaryKeyConstraint('content_id', 'topic_id')
    )
    op.create_table('entitylocation',
    sa.Column('entity_id', sa.Uuid(), nullable=False),
    sa.Column('location_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['entity_id'], ['entity.id'], ),
    sa.ForeignKeyConstraint(['location_id'], ['location.id'], ),
    sa.PrimaryKeyConstraint('entity_id', 'location_id')
    )
    op.create_table('mediadetails',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('content_id', sa.Uuid(), nullable=False),
    sa.Column('duration', sa.Float(), nullable=True),
    sa.Column('transcribed_text', sa.Text(), nullable=True),
    sa.Column('captions', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['content_id'], ['content.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('xclassification',
    sa.Column('content_id', sa.Uuid(), nullable=False),
    sa.Column('dimension_id', sa.Uuid(), nullable=False),
    sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['content_id'], ['content.id'], ),
    sa.ForeignKeyConstraint(['dimension_id'], ['classificationdimension.id'], ),
    sa.PrimaryKeyConstraint('content_id', 'dimension_id')
    )
    op.create_table('image',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('media_details_id', sa.Uuid(), nullable=False),
    sa.Column('image_url', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('caption', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('embeddings', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
    sa.ForeignKeyConstraint(['media_details_id'], ['mediadetails.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_image_image_url'), 'image', ['image_url'], unique=True)
    op.create_index(op.f('ix_image_media_details_id'), 'image', ['media_details_id'], unique=False)
    op.create_table('videoframe',
    sa.Column('media_details_id', sa.Uuid(), nullable=False),
    sa.Column('frame_number', sa.Integer(), nullable=False),
    sa.Column('frame_url', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('timestamp', sa.Float(), nullable=False),
    sa.Column('embeddings', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
    sa.ForeignKeyConstraint(['media_details_id'], ['mediadetails.id'], ),
    sa.PrimaryKeyConstraint('media_details_id', 'frame_number')
    )
    op.create_index(op.f('ix_videoframe_frame_url'), 'videoframe', ['frame_url'], unique=True)
    op.create_index(op.f('ix_videoframe_timestamp'), 'videoframe', ['timestamp'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_videoframe_timestamp'), table_name='videoframe')
    op.drop_index(op.f('ix_videoframe_frame_url'), table_name='videoframe')
    op.drop_table('videoframe')
    op.drop_index(op.f('ix_image_media_details_id'), table_name='image')
    op.drop_index(op.f('ix_image_image_url'), table_name='image')
    op.drop_table('image')
    op.drop_table('xclassification')
    op.drop_table('mediadetails')
    op.drop_table('entitylocation')
    op.drop_table('contenttopic')
    op.drop_table('contenttag')
    op.drop_index(op.f('ix_contentevaluation_rhetoric'), table_name='contentevaluation')
    op.drop_table('contentevaluation')
    op.drop_table('contententity')
    op.drop_index(op.f('ix_contentchunk_content_id'), table_name='contentchunk')
    op.drop_index(op.f('ix_contentchunk_chunk_number'), table_name='contentchunk')
    op.drop_table('contentchunk')
    op.drop_index(op.f('ix_topic_name'), table_name='topic')
    op.drop_index(op.f('ix_topic_content_count'), table_name='topic')
    op.drop_table('topic')
    op.drop_index(op.f('ix_tag_name'), table_name='tag')
    op.drop_table('tag')
    op.drop_index(op.f('ix_location_name'), table_name='location')
    op.drop_index(op.f('ix_location_location_type'), table_name='location')
    op.drop_table('location')
    op.drop_index(op.f('ix_entity_name'), table_name='entity')
    op.drop_index(op.f('ix_entity_entity_type'), table_name='entity')
    op.drop_table('entity')
    op.drop_index(op.f('ix_content_url'), table_name='content')
    op.drop_index(op.f('ix_content_title'), table_name='content')
    op.drop_index(op.f('ix_content_source'), table_name='content')
    op.drop_index(op.f('ix_content_publication_date'), table_name='content')
    op.drop_index(op.f('ix_content_insertion_date'), table_name='content')
    op.drop_index(op.f('ix_content_content_language'), table_name='content')
    op.drop_index(op.f('ix_content_author'), table_name='content')
    op.drop_table('content')
    op.drop_index(op.f('ix_classificationdimension_type'), table_name='classificationdimension')
    op.drop_index(op.f('ix_classificationdimension_name'), table_name='classificationdimension')
    op.drop_table('classificationdimension')
    # ### end Alembic commands ###