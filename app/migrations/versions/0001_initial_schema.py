from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
    )
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)

    op.create_table(
        "warehouses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "(is_active AND archived_at IS NULL) OR "
            "(NOT is_active AND archived_at IS NOT NULL)",
            name=op.f("ck_warehouses_archive_state_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_warehouses"),
    )
    op.create_index("ix_warehouses_name", "warehouses", ["name"], unique=True)

    op.create_table(
        "inventories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column(
            "physical_quantity",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "reserved_quantity",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        *timestamp_columns(),
        sa.CheckConstraint(
            "physical_quantity >= 0",
            name=op.f("ck_inventories_physical_quantity_non_negative"),
        ),
        sa.CheckConstraint(
            "reserved_quantity >= 0",
            name=op.f("ck_inventories_reserved_quantity_non_negative"),
        ),
        sa.CheckConstraint(
            "reserved_quantity <= physical_quantity",
            name=op.f("ck_inventories_reserved_not_above_physical"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_inventories_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_inventories_warehouse_id_warehouses",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inventories"),
        sa.UniqueConstraint(
            "product_id",
            "warehouse_id",
            name="uq_inventories_product_warehouse",
        ),
    )
    op.create_index(
        "ix_inventories_product_id",
        "inventories",
        ["product_id"],
    )
    op.create_index(
        "ix_inventories_warehouse_id",
        "inventories",
        ["warehouse_id"],
    )

    op.create_table(
        "fbs_reservations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("order_reference", sa.String(length=128), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="RESERVED",
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "quantity > 0",
            name=op.f("ck_fbs_reservations_quantity_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('RESERVED', 'CANCELLED', 'SHIPPED')",
            name=op.f("ck_fbs_reservations_reservation_status"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_fbs_reservations_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_fbs_reservations_warehouse_id_warehouses",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_fbs_reservations"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_fbs_reservations_idempotency_key",
        ),
    )
    op.create_index(
        "ix_fbs_reservations_order_reference",
        "fbs_reservations",
        ["order_reference"],
    )
    op.create_index(
        "ix_fbs_reservations_product_id",
        "fbs_reservations",
        ["product_id"],
    )
    op.create_index(
        "ix_fbs_reservations_warehouse_id",
        "fbs_reservations",
        ["warehouse_id"],
    )

    op.create_table(
        "transfers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("source_warehouse_id", sa.Integer(), nullable=False),
        sa.Column("destination_warehouse_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="CREATED",
        ),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "quantity > 0",
            name=op.f("ck_transfers_quantity_positive"),
        ),
        sa.CheckConstraint(
            "source_warehouse_id <> destination_warehouse_id",
            name=op.f("ck_transfers_different_warehouses"),
        ),
        sa.CheckConstraint(
            "status IN ('CREATED', 'IN_TRANSIT', 'RECEIVED')",
            name=op.f("ck_transfers_transfer_status"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_transfers_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_warehouse_id"],
            ["warehouses.id"],
            name="fk_transfers_source_warehouse_id_warehouses",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["destination_warehouse_id"],
            ["warehouses.id"],
            name="fk_transfers_destination_warehouse_id_warehouses",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transfers"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_transfers_idempotency_key",
        ),
    )
    op.create_index("ix_transfers_product_id", "transfers", ["product_id"])
    op.create_index(
        "ix_transfers_source_warehouse_id",
        "transfers",
        ["source_warehouse_id"],
    )
    op.create_index(
        "ix_transfers_destination_warehouse_id",
        "transfers",
        ["destination_warehouse_id"],
    )

    op.create_table(
        "shipments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("shipment_type", sa.String(length=16), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("source_warehouse_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=True),
        sa.Column("destination", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="CREATED",
        ),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "quantity > 0",
            name=op.f("ck_shipments_quantity_positive"),
        ),
        sa.CheckConstraint(
            "shipment_type IN ('FBS', 'FBO')",
            name=op.f("ck_shipments_shipment_type"),
        ),
        sa.CheckConstraint(
            "status IN ('CREATED', 'IN_TRANSIT', 'RECEIVED')",
            name=op.f("ck_shipments_shipment_status"),
        ),
        sa.CheckConstraint(
            "(shipment_type = 'FBS' AND reservation_id IS NOT NULL) OR "
            "(shipment_type = 'FBO' AND reservation_id IS NULL)",
            name=op.f("ck_shipments_reservation_matches_type"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_shipments_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_warehouse_id"],
            ["warehouses.id"],
            name="fk_shipments_source_warehouse_id_warehouses",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["fbs_reservations.id"],
            name="fk_shipments_reservation_id_fbs_reservations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_shipments"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_shipments_idempotency_key",
        ),
        sa.UniqueConstraint(
            "reservation_id",
            name="uq_shipments_reservation_id",
        ),
    )
    op.create_index("ix_shipments_product_id", "shipments", ["product_id"])
    op.create_index(
        "ix_shipments_source_warehouse_id",
        "shipments",
        ["source_warehouse_id"],
    )

    op.create_table(
        "stock_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("source_warehouse_id", sa.Integer(), nullable=True),
        sa.Column("destination_warehouse_id", sa.Integer(), nullable=True),
        sa.Column("reference_type", sa.String(length=64), nullable=True),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name=op.f("ck_stock_events_quantity_positive"),
        ),
        sa.CheckConstraint(
            "event_type IN ('RECEIPT', 'FBS_RESERVED', "
            "'FBS_RESERVATION_CANCELLED', 'FBS_SHIPPED', "
            "'TRANSFER_SHIPPED', 'TRANSFER_RECEIVED', "
            "'FBO_SHIPPED', 'FBO_RECEIVED')",
            name=op.f("ck_stock_events_stock_event_type"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_stock_events_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_warehouse_id"],
            ["warehouses.id"],
            name="fk_stock_events_source_warehouse_id_warehouses",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["destination_warehouse_id"],
            ["warehouses.id"],
            name="fk_stock_events_destination_warehouse_id_warehouses",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_events"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_stock_events_idempotency_key",
        ),
    )
    op.create_index(
        "ix_stock_events_event_type",
        "stock_events",
        ["event_type"],
    )
    op.create_index(
        "ix_stock_events_created_at",
        "stock_events",
        ["created_at"],
    )
    op.create_index(
        "ix_stock_events_reference",
        "stock_events",
        ["reference_type", "reference_id"],
    )
    op.create_index(
        "ix_stock_events_product_created",
        "stock_events",
        ["product_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("stock_events")
    op.drop_table("shipments")
    op.drop_table("transfers")
    op.drop_table("fbs_reservations")
    op.drop_table("inventories")
    op.drop_table("warehouses")
    op.drop_table("products")
