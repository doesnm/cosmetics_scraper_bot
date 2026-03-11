from decimal import Decimal
from decimal import Decimal
from sqlalchemy import Numeric, String, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.database.base import Base, TimestampMixin


class ProductORM(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    gender: Mapped[str] = mapped_column(String(20), default="unisex", nullable=False)

    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    rating: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=0.0)

    description: Mapped[str] = mapped_column(String, default="")
    attributes: Mapped[dict] = mapped_column(JSONB, server_default="{}")

    image_url: Mapped[str | None] = mapped_column(String, default=None)
    tg_file_id: Mapped[str | None] = mapped_column(String, default=None)

    __table_args__ = (
        Index("ix_products_attributes", "attributes", postgresql_using="gin"),
    )
