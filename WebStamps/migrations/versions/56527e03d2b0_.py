"""empty message

Revision ID: 56527e03d2b0
Revises: None
Create Date: 2016-05-30 11:54:34.164000

"""

# revision identifiers, used by Alembic.
revision = '56527e03d2b0'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('regular',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('frequency', sa.Integer(), nullable=True),
    sa.Column('author_id', sa.Integer(), nullable=True),
    sa.Column('post_id', sa.Integer(), nullable=True),
    sa.Column('usa', sa.Boolean(), nullable=True),
    sa.Column('uk', sa.Boolean(), nullable=True),
    sa.Column('china', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_regular_timestamp', 'regular', ['timestamp'], unique=False)
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_regular_timestamp', 'regular')
    op.drop_table('regular')
    ### end Alembic commands ###
