"""stripe: customer / subscription / invoice ids"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("stripe_customer_id", sa.String(64)))
    op.create_unique_constraint("uq_user_profiles_stripe_customer_id", "user_profiles", ["stripe_customer_id"])
    op.add_column("subscriptions", sa.Column("stripe_subscription_id", sa.String(64)))
    op.create_unique_constraint("uq_subscriptions_stripe_subscription_id", "subscriptions", ["stripe_subscription_id"])
    op.add_column("payments", sa.Column("external_id", sa.String(64)))
    op.create_unique_constraint("uq_payments_external_id", "payments", ["external_id"])


def downgrade() -> None:
    op.drop_constraint("uq_payments_external_id", "payments")
    op.drop_column("payments", "external_id")
    op.drop_constraint("uq_subscriptions_stripe_subscription_id", "subscriptions")
    op.drop_column("subscriptions", "stripe_subscription_id")
    op.drop_constraint("uq_user_profiles_stripe_customer_id", "user_profiles")
    op.drop_column("user_profiles", "stripe_customer_id")
