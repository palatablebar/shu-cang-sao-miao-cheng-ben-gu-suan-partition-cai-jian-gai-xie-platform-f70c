"""TableMeta / column / partition schemas."""
from pydantic import BaseModel, Field


class ColumnOut(BaseModel):
    id: int
    name: str
    data_type: str
    bytes: int
    byte_ratio: float
    ordinal: int
    is_partition_key: bool
    note: str


class PartitionOut(BaseModel):
    id: int
    dt: str
    bytes: int
    row_count: int
    file_count: int
    is_current: bool


class TableListItem(BaseModel):
    id: int
    schema_name: str
    table_name: str
    layer: str
    storage_format: str
    partition_key: str
    partition_count: int
    row_count: int
    total_bytes: int
    data_column_count: int
    owner: str
    description: str
    suggested_columns: list[str]
    query_count: int = 0
    blocked_query_count: int = 0


class TableDetail(TableListItem):
    columns: list[ColumnOut]
    partitions: list[PartitionOut]


class TableUpdateRequest(BaseModel):
    owner: str | None = None
    description: str | None = None
    suggested_columns: list[str] | None = Field(default=None, max_length=64)
