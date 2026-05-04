"""add multi-user auth isolation schema

Revision ID: 016
Revises: c153f8c4e111
Create Date: 2026-05-03

"""
from alembic import op
from alembic.util import CommandError
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '016'
down_revision = 'c153f8c4e111'
branch_labels = None
depends_on = None


OWNER_TABLES = (
    'projects',
    'user_templates',
    'materials',
    'reference_files',
    'tasks',
)

NAMING_CONVENTION = {
    'ix': 'ix_%(table_name)s_%(column_0_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
}


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _has_table(table_name: str) -> bool:
    return table_name in _table_names()


def _column_names(table_name: str) -> set[str]:
    if not _has_table(table_name):
        return set()
    return {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _column_nullable(table_name: str, column_name: str) -> bool:
    for column in sa.inspect(op.get_bind()).get_columns(table_name):
        if column['name'] == column_name:
            return bool(column['nullable'])
    return True


def _index_names(table_name: str) -> set[str]:
    if not _has_table(table_name):
        return set()
    return {index['name'] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _has_user_fk(table_name: str) -> bool:
    return _user_fk_name(table_name) is not None


def _table_has_rows(table_name: str) -> bool:
    if not _has_table(table_name):
        return False
    result = op.get_bind().execute(sa.text(f'SELECT 1 FROM {table_name} LIMIT 1'))
    return result.first() is not None


def _guard_destructive_downgrade() -> None:
    populated_tables = [
        table_name
        for table_name in ('users', 'user_settings')
        if _table_has_rows(table_name)
    ]
    if populated_tables:
        names = ', '.join(populated_tables)
        raise CommandError(f'Refusing to downgrade auth migration with data in: {names}')


def _user_fk_name(table_name: str) -> str | None:
    if not _has_table(table_name):
        return None
    for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table_name):
        if (
            foreign_key.get('referred_table') == 'users'
            and foreign_key.get('constrained_columns') == ['user_id']
        ):
            return foreign_key.get('name') or f'fk_{table_name}_user_id_users'
    return None


def upgrade() -> None:
    if not _has_table('users'):
        op.create_table(
            'users',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=True),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
    if _has_table('users') and 'ix_users_email' not in _index_names('users'):
        op.create_index('ix_users_email', 'users', ['email'], unique=True)

    if not _has_table('user_settings'):
        op.create_table(
            'user_settings',
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('ai_provider_format', sa.String(length=20), nullable=True),
            sa.Column('api_base_url', sa.String(length=500), nullable=True),
            sa.Column('api_key', sa.String(length=500), nullable=True),
            sa.Column('text_model', sa.String(length=100), nullable=True),
            sa.Column('image_model', sa.String(length=100), nullable=True),
            sa.Column('image_caption_model', sa.String(length=100), nullable=True),
            sa.Column('output_language', sa.String(length=10), nullable=True),
            sa.Column('description_generation_mode', sa.String(length=20), nullable=True),
            sa.Column('enable_text_reasoning', sa.Boolean(), nullable=False),
            sa.Column('text_thinking_budget', sa.Integer(), nullable=False),
            sa.Column('enable_image_reasoning', sa.Boolean(), nullable=False),
            sa.Column('image_thinking_budget', sa.Integer(), nullable=False),
            sa.Column('text_model_source', sa.String(length=50), nullable=True),
            sa.Column('image_model_source', sa.String(length=50), nullable=True),
            sa.Column('image_caption_model_source', sa.String(length=50), nullable=True),
            sa.Column('lazyllm_api_keys', sa.Text(), nullable=True),
            sa.Column('text_api_key', sa.String(length=500), nullable=True),
            sa.Column('text_api_base_url', sa.String(length=500), nullable=True),
            sa.Column('image_api_key', sa.String(length=500), nullable=True),
            sa.Column('image_api_base_url', sa.String(length=500), nullable=True),
            sa.Column('image_caption_api_key', sa.String(length=500), nullable=True),
            sa.Column('image_caption_api_base_url', sa.String(length=500), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('user_id'),
        )

    for table_name in OWNER_TABLES:
        if not _has_table(table_name):
            continue

        columns = _column_names(table_name)
        has_user_id = 'user_id' in columns
        has_user_fk = _has_user_fk(table_name)
        has_user_index = f'ix_{table_name}_user_id' in _index_names(table_name)
        needs_nullable_project = (
            table_name == 'tasks'
            and 'project_id' in columns
            and not _column_nullable('tasks', 'project_id')
        )

        if has_user_id and has_user_fk and has_user_index and not needs_nullable_project:
            continue

        with op.batch_alter_table(table_name, naming_convention=NAMING_CONVENTION) as batch_op:
            if not has_user_id:
                batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
            if not has_user_fk:
                batch_op.create_foreign_key(
                    f'fk_{table_name}_user_id_users',
                    'users',
                    ['user_id'],
                    ['id'],
                )
            if not has_user_index:
                batch_op.create_index(f'ix_{table_name}_user_id', ['user_id'], unique=False)
            if needs_nullable_project:
                batch_op.alter_column(
                    'project_id',
                    existing_type=sa.String(length=36),
                    nullable=True,
                )


def downgrade() -> None:
    _guard_destructive_downgrade()

    for table_name in reversed(OWNER_TABLES):
        if not _has_table(table_name):
            continue

        columns = _column_names(table_name)
        has_user_id = 'user_id' in columns
        user_fk_name = _user_fk_name(table_name)
        has_user_index = f'ix_{table_name}_user_id' in _index_names(table_name)
        needs_required_project = (
            table_name == 'tasks'
            and 'project_id' in columns
            and _column_nullable('tasks', 'project_id')
        )

        if not has_user_id and not user_fk_name and not has_user_index and not needs_required_project:
            continue

        with op.batch_alter_table(table_name, naming_convention=NAMING_CONVENTION) as batch_op:
            if needs_required_project:
                batch_op.alter_column(
                    'project_id',
                    existing_type=sa.String(length=36),
                    nullable=False,
                )
            if has_user_index:
                batch_op.drop_index(f'ix_{table_name}_user_id')
            if user_fk_name:
                batch_op.drop_constraint(user_fk_name, type_='foreignkey')
            if has_user_id:
                batch_op.drop_column('user_id')

    if _has_table('user_settings'):
        op.drop_table('user_settings')
    if _has_table('users'):
        if 'ix_users_email' in _index_names('users'):
            op.drop_index('ix_users_email', table_name='users')
        op.drop_table('users')
