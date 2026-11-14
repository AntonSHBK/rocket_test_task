from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_stock_event_labels"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stock_events",
        sa.Column("product_sku", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "stock_events",
        sa.Column("source_label", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "stock_events",
        sa.Column("destination_label", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
        UPDATE stock_events AS event
        SET product_sku = product.sku
        FROM products AS product
        WHERE event.product_id = product.id
        """
    )
    op.alter_column("stock_events", "product_sku", nullable=False)
    op.execute(
        """
        UPDATE stock_events AS event
        SET source_label = warehouse.name
        FROM warehouses AS warehouse
        WHERE event.source_warehouse_id = warehouse.id
        """
    )
    op.execute(
        """
        UPDATE stock_events AS event
        SET destination_label = warehouse.name
        FROM warehouses AS warehouse
        WHERE event.destination_warehouse_id = warehouse.id
        """
    )
    op.execute(
        """
        UPDATE stock_events
        SET source_label = 'Поставка'
        WHERE event_type = 'RECEIPT' AND source_label IS NULL
        """
    )
    op.execute(
        """
        UPDATE stock_events
        SET destination_label = 'Резерв FBS'
        WHERE event_type = 'FBS_RESERVED' AND destination_label IS NULL
        """
    )
    op.execute(
        """
        UPDATE stock_events
        SET destination_label = source_label,
            source_label = 'Резерв FBS'
        WHERE event_type = 'FBS_RESERVATION_CANCELLED'
        """
    )
    op.execute(
        """
        UPDATE stock_events AS event
        SET destination_label = COALESCE(reservation.order_reference, 'Клиент')
        FROM fbs_reservations AS reservation
        WHERE event.event_type = 'FBS_SHIPPED'
          AND event.reference_type = 'fbs_reservation'
          AND event.reference_id = reservation.id
        """
    )
    op.execute(
        """
        UPDATE stock_events AS event
        SET destination_label = shipment.destination
        FROM shipments AS shipment
        WHERE event.event_type IN ('FBO_SHIPPED', 'FBO_RECEIVED')
          AND event.reference_type = 'fbo_shipment'
          AND event.reference_id = shipment.id
        """
    )
    op.execute(
        """
        UPDATE stock_events
        SET source_label = 'В пути: ' || destination_label
        WHERE event_type = 'FBO_RECEIVED'
          AND destination_label IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("stock_events", "destination_label")
    op.drop_column("stock_events", "source_label")
    op.drop_column("stock_events", "product_sku")
