"""initial
  schema

Revision ID: cddef4fad456
Revises:
Create Date: 2026-03-23 05:27:35.484900

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cddef4fad456'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('satellite_images',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('storage_path', sa.String(length=500), nullable=False),
    sa.Column('cloud_cover_pct', sa.Float(), nullable=False),
    sa.Column('resolution_meters', sa.Float(), nullable=False),
    sa.Column('bounds', geoalchemy2.types.Geometry(geometry_type='POLYGON', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('is_usable', sa.Boolean(), nullable=False),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    # NOTE: idx_satellite_images_bounds is auto-created by GeoAlchemy2 event hooks
    op.create_index(op.f('ix_satellite_images_captured_at'), 'satellite_images', ['captured_at'], unique=False)
    op.create_table('zones',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('geometry', geoalchemy2.types.Geometry(geometry_type='POLYGON', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    # NOTE: idx_zones_geometry is auto-created by GeoAlchemy2 event hooks
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('username', sa.String(length=100), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('role', sa.Enum('reviewer', 'admin', 'super_admin', name='user_role'), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('zone_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['zone_id'], ['zones.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('construction_spots',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('geometry', geoalchemy2.types.Geometry(geometry_type='POLYGON', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('status', sa.Enum('flagged', 'legal', 'illegal', 'resolved', 'review_pending', name='spot_status'), nullable=False),
    sa.Column('first_detected_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_detected_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('grace_period_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('review_prompted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('confidence_score', sa.Float(), nullable=False),
    sa.Column('change_type', sa.Enum('excavation', 'foundation', 'new_structure', 'extension', 'land_clearing', name='change_type'), nullable=True),
    sa.Column('reviewed_by_id', sa.UUID(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('assigned_to_id', sa.UUID(), nullable=True),
    sa.Column('previous_spot_id', sa.UUID(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['previous_spot_id'], ['construction_spots.id'], ),
    sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # NOTE: idx_construction_spots_geometry is auto-created by GeoAlchemy2 event hooks
    op.create_table('notifications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('message', sa.String(length=500), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('audit_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('officer_id', sa.UUID(), nullable=False),
    sa.Column('spot_id', sa.UUID(), nullable=False),
    sa.Column('action', sa.Enum('marked_legal', 'marked_illegal', 'marked_resolved', 're_approved', 're_flagged', name='audit_action'), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['officer_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['spot_id'], ['construction_spots.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('detections',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('spot_id', sa.UUID(), nullable=False),
    sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('comparison_interval', sa.Enum('1d', '7d', '15d', '30d', name='comparison_interval'), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('image_before_id', sa.UUID(), nullable=False),
    sa.Column('image_after_id', sa.UUID(), nullable=False),
    sa.Column('change_mask_path', sa.String(length=500), nullable=False),
    sa.Column('area_sq_meters', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['image_after_id'], ['satellite_images.id'], ),
    sa.ForeignKeyConstraint(['image_before_id'], ['satellite_images.id'], ),
    sa.ForeignKeyConstraint(['spot_id'], ['construction_spots.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('detections')
    op.drop_table('audit_logs')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('construction_spots')
    op.drop_table('users')
    op.drop_table('zones')
    op.drop_index(op.f('ix_satellite_images_captured_at'), table_name='satellite_images')
    op.drop_table('satellite_images')
    sa.Enum(name='audit_action').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='comparison_interval').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='change_type').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='spot_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='user_role').drop(op.get_bind(), checkfirst=True)
