"""Fix telegram_channel_id and telegram_chat_id to BigInteger

Revision ID: 002_fix_telegram_ids_to_bigint
Revises: 001_fix_user_id_type
Create Date: 2025-11-07 11:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import INTEGER

# revision identifiers, used by Alembic.
revision = '002_fix_telegram_ids_to_bigint'
down_revision = '001_fix_user_id_type'
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Upgrade: Change telegram_channel_id and telegram_chat_id to BigInteger"""
    # For PostgreSQL, we need to:
    # 1. Create temporary columns with BigInteger type
    # 2. Copy data
    # 3. Drop the old Integer columns
    # 4. Rename the temporary columns

    # CHANNELS TABLE
    # Add temporary columns with BigInteger type
    op.add_column('channels', sa.Column('telegram_channel_id_temp', sa.BigInteger, nullable=True))
    op.add_column('channels', sa.Column('telegram_chat_id_temp', sa.BigInteger, nullable=True))

    # Copy data from old columns to new columns
    op.execute('UPDATE channels SET telegram_channel_id_temp = telegram_channel_id')
    op.execute('UPDATE channels SET telegram_chat_id_temp = telegram_chat_id')

    # Drop the old Integer columns
    op.drop_column('channels', 'telegram_channel_id')
    op.drop_column('channels', 'telegram_chat_id')

    # Rename temporary columns to original names
    op.alter_column('channels', 'telegram_channel_id_temp', new_column_name='telegram_channel_id')
    op.alter_column('channels', 'telegram_chat_id_temp', new_column_name='telegram_chat_id')

    # Add NOT NULL constraint
    op.alter_column('channels', 'telegram_channel_id', nullable=False)
    op.alter_column('channels', 'telegram_chat_id', nullable=False)



def downgrade() -> None:
    """Downgrade: Change telegram_channel_id and telegram_chat_id back to Integer"""
    # For PostgreSQL, we need to:
    # 1. Create temporary columns with Integer type
    # 2. Copy data
    # 3. Drop the new BigInteger columns
    # 4. Rename the temporary columns
    
    # CHANNELS TABLE
    # Add temporary columns with Integer type
    op.add_column('channels', sa.Column('telegram_channel_id_temp', sa.Integer, nullable=True))
    op.add_column('channels', sa.Column('telegram_chat_id_temp', sa.Integer, nullable=True))

    # Copy data from BigInteger columns to Integer columns (with casting)
    op.execute('UPDATE channels SET telegram_channel_id_temp = CAST(telegram_channel_id AS INTEGER)')
    op.execute('UPDATE channels SET telegram_chat_id_temp = CAST(telegram_chat_id AS INTEGER)')

    # Drop the BigInteger columns
    op.drop_column('channels', 'telegram_channel_id')
    op.drop_column('channels', 'telegram_chat_id')
    
    # Rename temporary columns to original names
    op.alter_column('channels', 'telegram_channel_id_temp', new_column_name='telegram_channel_id')
    op.alter_column('channels', 'telegram_chat_id_temp', new_column_name='telegram_chat_id')
    
    # Add NOT NULL constraint
    op.alter_column('channels', 'telegram_channel_id', nullable=False)
    op.alter_column('channels', 'telegram_chat_id', nullable=False)