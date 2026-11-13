# migrations

`0001_initial.sql` 是 `src/models/` 的 DDL 快照（由 SQLAlchemy 元数据导出），仅用于人工评审与 DBA 预建库。

运行时由 `src.config.database.init_db()` 调用 `Base.metadata.create_all()` 幂等建表，
因此容器启动不需要额外的迁移步骤；如需真正的版本化迁移，可在此目录接 Alembic。
