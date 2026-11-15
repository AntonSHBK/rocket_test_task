from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_fbs_delivery"
down_revision: str | None = "0003_write_off"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_EVENT_TYPES = (
    "RECEIPT",
    "WRITE_OFF",
    "FBS_RESERVED",
    "FBS_RESERVATION_CANCELLED",
    "FBS_SHIPPED",
    "TRANSFER_SHIPPED",
    "TRANSFER_RECEIVED",
    "FBO_SHIPPED",
    "FBO_RECEIVED",
)
NEW_EVENT_TYPES = (*OLD_EVENT_TYPES[:5], "FBS_DELIVERED", *OLD_EVENT_TYPES[5:])


def _event_type_values(event_types: tuple[str, ...]) -> str:
    return ", ".join(f"'{event_type}'" for event_type in event_types)


def upgrade() -> None:
    op.add_column(
        "fbs_reservations",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_constraint(
        op.f("ck_fbs_reservations_reservation_status"),
        "fbs_reservations",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_fbs_reservations_reservation_status"),
        "fbs_reservations",
        "status IN ('RESERVED', 'CANCELLED', 'SHIPPED', 'DELIVERED')",
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
    op.execute("DELETE FROM stock_events WHERE event_type = 'FBS_DELIVERED'")
    op.execute(
        """
        UPDATE shipments
        SET status = 'IN_TRANSIT', received_at = NULL
        WHERE shipment_type = 'FBS'
          AND reservation_id IN (
              SELECT id
              FROM fbs_reservations
              WHERE status = 'DELIVERED'
          )
        """
    )
    op.execute(
        """
        UPDATE fbs_reservations
        SET status = 'SHIPPED'
        WHERE status = 'DELIVERED'
        """
    )
    op.drop_constraint(
        op.f("ck_stock_events_stock_event_type"),
        "stock_events",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_stock_events_stock_event_type"),
        "stock_events",
        f"event_type IN ({_event_type_values(OLD_EVENT_TYPES)})",
    )
    op.drop_constraint(
        op.f("ck_fbs_reservations_reservation_status"),
        "fbs_reservations",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_fbs_reservations_reservation_status"),
        "fbs_reservations",
        "status IN ('RESERVED', 'CANCELLED', 'SHIPPED')",
    )
    op.drop_column("fbs_reservations", "delivered_at")
