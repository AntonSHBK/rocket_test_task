from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_write_off"
down_revision: str | None = "0002_stock_event_labels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_EVENT_TYPES = (
    "RECEIPT",
    "FBS_RESERVED",
    "FBS_RESERVATION_CANCELLED",
    "FBS_SHIPPED",
    "TRANSFER_SHIPPED",
    "TRANSFER_RECEIVED",
    "FBO_SHIPPED",
    "FBO_RECEIVED",
)
NEW_EVENT_TYPES = ("RECEIPT", "WRITE_OFF", *OLD_EVENT_TYPES[1:])


def _event_type_values(event_types: tuple[str, ...]) -> str:
    return ", ".join(f"'{event_type}'" for event_type in event_types)


def upgrade() -> None:
    op.add_column(
        "stock_events",
        sa.Column("reason", sa.String(length=500), nullable=True),
    )
    op.drop_constraint(
        op.f("ck_stock_events_stock_event_type"),
        "stock_events",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_stock_events_stock_event_type"),
        "stock_events",
        f"event_type IN ({_event_type_values(NEW_EVENT_TYPES)})",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_stock_events_stock_event_type"),
        "stock_events",
        type_="check",
    )
    op.execute("DELETE FROM stock_events WHERE event_type = 'WRITE_OFF'")
    op.create_check_constraint(
        op.f("ck_stock_events_stock_event_type"),
        "stock_events",
        f"event_type IN ({_event_type_values(OLD_EVENT_TYPES)})",
    )
    op.drop_column("stock_events", "reason")
