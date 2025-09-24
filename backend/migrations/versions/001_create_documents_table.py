"""Create documents table

Revision ID: 001
Revises: 
Create Date: 2024-09-24 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create documents table."""
    op.create_table(
        'documents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('page_count', sa.Integer()),
        sa.Column('text_content_length', sa.BigInteger()),
        sa.Column('upload_timestamp', sa.DateTime(), nullable=False),
        sa.Column('processing_status', sa.String(50), nullable=False, server_default='uploaded'),
        sa.Column('storage_path', sa.String(500), nullable=False),
        sa.Column('metadata', JSON()),
    )
    
    # Create indexes for common queries
    op.create_index('ix_documents_processing_status', 'documents', ['processing_status'])
    op.create_index('ix_documents_upload_timestamp', 'documents', ['upload_timestamp'])
    op.create_index('ix_documents_filename', 'documents', ['filename'])
    op.create_index('ix_documents_original_filename', 'documents', ['original_filename'])


def downgrade() -> None:
    """Drop documents table."""
    op.drop_index('ix_documents_original_filename')
    op.drop_index('ix_documents_filename') 
    op.drop_index('ix_documents_upload_timestamp')
    op.drop_index('ix_documents_processing_status')
    op.drop_table('documents')