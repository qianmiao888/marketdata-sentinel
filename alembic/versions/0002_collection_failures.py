"""Allow collection failures before a snapshot can be established."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ingestion_runs") as batch:
        batch.alter_column("snapshot_id", nullable=True)


def downgrade():
    # Failed preflight runs have no input version; deleting them requires explicit operator action.
    with op.batch_alter_table("ingestion_runs") as batch:
        batch.alter_column("snapshot_id", nullable=False)
