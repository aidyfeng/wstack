# 数据库建模

写 Repository、加表加列、建索引、写 Alembic 迁移、划事务边界时，读 `standard-sqlalchemy-persistence`。

领域实体和 ORM 模型分开。生产库是 PostgreSQL。SQLite 上测试全绿不代表迁移、约束和条件索引在 PostgreSQL 上成立。

模块该落在哪一层见 [structure](structure.md)。这篇只定数据怎么存。
