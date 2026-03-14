"""Phase 43: Add performance indexes

Revision ID: j7k8l9m0n1o2
Revises: i6j7k8l9m0n1
Create Date: 2025-03-14

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "j7k8l9m0n1o2"
down_revision = "i6j7k8l9m0n1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_webhook_deliveries_status_code", "webhook_deliveries", ["status_code"])
    op.create_index("ix_password_reset_tokens_email", "password_reset_tokens", ["email"])
    op.create_index("ix_data_reviews_status", "data_reviews", ["status"])


def downgrade() -> None:
    op.drop_index("ix_data_reviews_status", table_name="data_reviews")
    op.drop_index("ix_password_reset_tokens_email", table_name="password_reset_tokens")
    op.drop_index("ix_webhook_deliveries_status_code", table_name="webhook_deliveries")
