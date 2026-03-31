"""add trip albums

Revision ID: a3f7c2d89e01
Revises: 75d48eb17ca2
Create Date: 2026-03-31 16:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7c2d89e01'
down_revision: Union[str, Sequence[str], None] = '75d48eb17ca2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Trips table ---
    op.create_table(
        'trips',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('start_date', sa.String(length=10), nullable=True),
        sa.Column('end_date', sa.String(length=10), nullable=True),
        sa.Column('cover_media_id', sa.String(length=36), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.Column('visibility', sa.String(length=20), nullable=False, server_default='members'),
        sa.Column('invite_token', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['cover_media_id'], ['media.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['persons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invite_token'),
    )

    # --- Trip participants ---
    op.create_table(
        'trip_participants',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('trip_id', sa.String(length=36), nullable=False),
        sa.Column('person_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='contributor'),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trip_id', 'person_id', name='uq_trip_participant'),
    )

    # --- Trip moments junction ---
    op.create_table(
        'trip_moments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('trip_id', sa.String(length=36), nullable=False),
        sa.Column('moment_id', sa.String(length=36), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=False),
        sa.Column('added_by', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['moment_id'], ['moments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trip_id', 'moment_id', name='uq_trip_moment'),
    )

    # --- Add location + EXIF + upload columns to media ---
    with op.batch_alter_table('media') as batch_op:
        batch_op.add_column(sa.Column('location_lat', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('location_lng', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('location_alt', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('taken_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('taken_at_source', sa.String(30), nullable=True))
        batch_op.add_column(sa.Column('camera_make', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('camera_model', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('orientation', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('has_exif', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('video_codec', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('video_thumbnail_path', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('resized_path', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('resized_width', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('resized_height', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('resized_size_bytes', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('upload_id', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('upload_complete', sa.Boolean(), nullable=True, server_default='1'))


def downgrade() -> None:
    op.drop_table('trip_moments')
    op.drop_table('trip_participants')
    op.drop_table('trips')

    with op.batch_alter_table('media') as batch_op:
        batch_op.drop_column('location_lat')
        batch_op.drop_column('location_lng')
        batch_op.drop_column('location_alt')
        batch_op.drop_column('taken_at')
        batch_op.drop_column('taken_at_source')
        batch_op.drop_column('camera_make')
        batch_op.drop_column('camera_model')
        batch_op.drop_column('orientation')
        batch_op.drop_column('has_exif')
        batch_op.drop_column('video_codec')
        batch_op.drop_column('video_thumbnail_path')
        batch_op.drop_column('resized_path')
        batch_op.drop_column('resized_width')
        batch_op.drop_column('resized_height')
        batch_op.drop_column('resized_size_bytes')
        batch_op.drop_column('upload_id')
        batch_op.drop_column('upload_complete')
