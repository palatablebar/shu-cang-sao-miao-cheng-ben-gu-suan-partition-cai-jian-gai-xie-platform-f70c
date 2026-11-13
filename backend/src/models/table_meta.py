"""TableMeta — 表 / 分区 / 列统计的聚合根（算法 1 的元数据输入）。"""
from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin


class TableMeta(Base, TimestampMixin):
    __tablename__ = "table_meta"

    id: Mapped[int] = mapped_column(primary_key=True)
    schema_name: Mapped[str] = mapped_column(String(64), nullable=False, default="lantu_ads")
    table_name: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    layer: Mapped[str] = mapped_column(String(8), nullable=False, default="DWD")
    storage_format: Mapped[str] = mapped_column(String(24), nullable=False, default="parquet")
    partition_key: Mapped[str] = mapped_column(String(32), nullable=False, default="dt")
    partition_type: Mapped[str] = mapped_column(String(16), nullable=False, default="date_str")
    partition_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    data_column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    owner: Mapped[str] = mapped_column(String(80), nullable=False, default="数据平台组")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    suggested_columns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    last_analyzed_dt: Mapped[str | None] = mapped_column(String(16), nullable=True)

    columns = relationship(
        "TableColumn", back_populates="table", cascade="all, delete-orphan", order_by="TableColumn.ordinal"
    )
    partitions = relationship(
        "PartitionMeta", back_populates="table", cascade="all, delete-orphan", order_by="PartitionMeta.dt"
    )


class TableColumn(Base, TimestampMixin):
    __tablename__ = "table_column"

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("table_meta.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False, default="string")
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    byte_ratio: Mapped[float] = mapped_column(nullable=False, default=0.0)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_partition_key: Mapped[bool] = mapped_column(nullable=False, default=False)
    note: Mapped[str] = mapped_column(String(160), nullable=False, default="")

    table = relationship("TableMeta", back_populates="columns")


class PartitionMeta(Base, TimestampMixin):
    __tablename__ = "partition_meta"

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("table_meta.id", ondelete="CASCADE"), index=True)
    dt: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    row_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_current: Mapped[bool] = mapped_column(nullable=False, default=False)

    table = relationship("TableMeta", back_populates="partitions")
