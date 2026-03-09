"""add_user_ownership_to_funding_programs_and_companies

Revision ID: f5c86d23bbfc
Revises: add_chat_history
Create Date: 2026-01-14 12:21:10.259792

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = 'f5c86d23bbfc'
down_revision: Union[str, None] = 'add_chat_history'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if we're using SQLite (which has limited ALTER TABLE support)
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    # Check if columns already exist (in case of partial migration)
    inspector = sa.inspect(bind)
    funding_programs_columns = [col['name'] for col in inspector.get_columns('funding_programs')]
    companies_columns = [col['name'] for col in inspector.get_columns('companies')]

    # Add user_email columns only if they don't exist
    if 'user_email' not in funding_programs_columns:
        op.add_column('funding_programs', sa.Column('user_email', sa.String(), nullable=True))
    if 'user_email' not in companies_columns:
        op.add_column('companies', sa.Column('user_email', sa.String(), nullable=True))

    # Handle existing records: assign them to the first user if users exist
    # This prevents data loss when migrating existing databases
    connection = op.get_bind()
    user_count = connection.execute(text("SELECT COUNT(*) FROM users")).scalar()
    if user_count and user_count > 0:
        # Users exist: assign existing records to the first user
        first_user_email = connection.execute(text("SELECT email FROM users ORDER BY email LIMIT 1")).scalar()
        if first_user_email:
            connection.execute(
                text("UPDATE funding_programs SET user_email = :email WHERE user_email IS NULL"),
                {"email": first_user_email}
            )
            connection.execute(
                text("UPDATE companies SET user_email = :email WHERE user_email IS NULL"),
                {"email": first_user_email}
            )
        else:
            # Edge case: users exist but no valid email found (shouldn't happen, but handle gracefully)
            # Delete orphaned records since we can't assign them to a user
            connection.execute(text("DELETE FROM funding_programs WHERE user_email IS NULL"))
            connection.execute(text("DELETE FROM companies WHERE user_email IS NULL"))
    else:
        # No users exist: safe to delete orphaned records (empty database scenario)
        connection.execute(text("DELETE FROM funding_programs WHERE user_email IS NULL"))
        connection.execute(text("DELETE FROM companies WHERE user_email IS NULL"))

    # Ensure no NULL values remain before setting NOT NULL constraint
    # This is a safety check to prevent migration failure
    null_funding_programs = connection.execute(text("SELECT COUNT(*) FROM funding_programs WHERE user_email IS NULL")).scalar()
    null_companies = connection.execute(text("SELECT COUNT(*) FROM companies WHERE user_email IS NULL")).scalar()
    if null_funding_programs > 0 or null_companies > 0:
        # If NULL values still exist, delete them to allow NOT NULL constraint
        connection.execute(text("DELETE FROM funding_programs WHERE user_email IS NULL"))
        connection.execute(text("DELETE FROM companies WHERE user_email IS NULL"))

    # For SQLite, we can't easily change nullability without recreating the table
    # The columns will remain nullable in SQLite but application enforces NOT NULL
    # For PostgreSQL, we can properly set NOT NULL
    if not is_sqlite:
        # PostgreSQL: Standard ALTER COLUMN works
        op.alter_column('funding_programs', 'user_email', nullable=False)
        op.alter_column('companies', 'user_email', nullable=False)

    # Add foreign key constraints
    # SQLite doesn't support adding FKs after table creation, so we skip for SQLite
    # The application will enforce referential integrity
    if not is_sqlite:
        # Check if foreign keys already exist
        funding_programs_fks = [fk['name'] for fk in inspector.get_foreign_keys('funding_programs')]
        companies_fks = [fk['name'] for fk in inspector.get_foreign_keys('companies')]

        # Add foreign key constraints only if they don't exist (PostgreSQL only)
        if 'fk_funding_programs_user_email' not in funding_programs_fks:
            op.create_foreign_key(
                'fk_funding_programs_user_email',
                'funding_programs',
                'users',
                ['user_email'],
                ['email']
            )
        if 'fk_companies_user_email' not in companies_fks:
            op.create_foreign_key(
                'fk_companies_user_email',
                'companies',
                'users',
                ['user_email'],
                ['email']
            )

    # Check if indexes already exist
    funding_programs_indexes = [idx['name'] for idx in inspector.get_indexes('funding_programs')]
    companies_indexes = [idx['name'] for idx in inspector.get_indexes('companies')]

    # Add indexes for performance only if they don't exist
    if 'ix_funding_programs_user_email' not in funding_programs_indexes:
        op.create_index(op.f('ix_funding_programs_user_email'), 'funding_programs', ['user_email'], unique=False)
    if 'ix_companies_user_email' not in companies_indexes:
        op.create_index(op.f('ix_companies_user_email'), 'companies', ['user_email'], unique=False)


def downgrade() -> None:
    # Check if we're using SQLite (which has limited ALTER TABLE support)
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    inspector = sa.inspect(bind)

    # Remove indexes only if they exist
    funding_programs_indexes = [idx['name'] for idx in inspector.get_indexes('funding_programs')]
    companies_indexes = [idx['name'] for idx in inspector.get_indexes('companies')]

    if 'ix_companies_user_email' in companies_indexes:
        op.drop_index(op.f('ix_companies_user_email'), table_name='companies')
    if 'ix_funding_programs_user_email' in funding_programs_indexes:
        op.drop_index(op.f('ix_funding_programs_user_email'), table_name='funding_programs')

    # Remove foreign key constraints only if they exist (PostgreSQL only)
    # SQLite doesn't support dropping FKs, and they weren't created for SQLite
    if not is_sqlite:
        funding_programs_fks = [fk['name'] for fk in inspector.get_foreign_keys('funding_programs')]
        companies_fks = [fk['name'] for fk in inspector.get_foreign_keys('companies')]

        if 'fk_companies_user_email' in companies_fks:
            op.drop_constraint('fk_companies_user_email', 'companies', type_='foreignkey')
        if 'fk_funding_programs_user_email' in funding_programs_fks:
            op.drop_constraint('fk_funding_programs_user_email', 'funding_programs', type_='foreignkey')

    # Remove columns only if they exist
    funding_programs_columns = [col['name'] for col in inspector.get_columns('funding_programs')]
    companies_columns = [col['name'] for col in inspector.get_columns('companies')]

    if 'user_email' in companies_columns:
        op.drop_column('companies', 'user_email')
    if 'user_email' in funding_programs_columns:
        op.drop_column('funding_programs', 'user_email')






