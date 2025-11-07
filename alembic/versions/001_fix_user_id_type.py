"""Change user_id from UUID to String in channels table

Revision ID: 001_fix_user_id_type
Revises: 
Create Date: 2025-11-07 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_fix_user_id_type'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade: Change user_id column from UUID to String(50)"""
    # For PostgreSQL, we need to:
    # 1. Create a temporary column with the new type
    # 2. Copy data (converting UUID to string)
    # 3. Drop the old column
    # 4. Rename the temporary column
    
    # Add temporary column with VARCHAR type
    op.add_column('channels', sa.Column('user_id_temp', sa.String(50), nullable=True))
    
    # Copy data from old column to new column (cast UUID to string)
    op.execute('UPDATE channels SET user_id_temp = CAST(user_id AS VARCHAR(50))')
    
    # Drop the old UUID column
    op.drop_column('channels', 'user_id')
    
    # Rename temporary column to original name
    op.alter_column('channels', 'user_id_temp', new_column_name='user_id')
    
    # Add NOT NULL constraint
    op.alter_column('channels', 'user_id', nullable=False)


def downgrade() -> None:
    """Downgrade: Change user_id column back to UUID"""
    # Add temporary column with UUID type
    op.add_column('channels', sa.Column('user_id_temp', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Copy data from string column to UUID column (cast string to UUID)
    op.execute('UPDATE channels SET user_id_temp = CAST(user_id AS UUID)')
    
    # Drop the string column
    op.drop_column('channels', 'user_id')
    
    # Rename temporary column to original name
    op.alter_column('channels', 'user_id_temp', new_column_name='user_id')
    
    # Add NOT NULL constraint
    op.alter_column('channels', 'user_id', nullable=False)