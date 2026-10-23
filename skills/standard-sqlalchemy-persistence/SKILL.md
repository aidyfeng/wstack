---
name: standard-sqlalchemy-persistence
description: >
  SQLAlchemy 2.0 async 持久层。写 Repository、加表加列、建索引、写 Alembic 迁移、划事务边界时使用。
---

# SQLAlchemy async 持久层

适用：SQLAlchemy 2.0 `AsyncSession`、Alembic、领域实体与 ORM 模型分开。生产是 PostgreSQL，测试可能是 SQLite。

## 共享 session 上顺序 await

同一请求内所有 repository 共用一个 `AsyncSession`。对这个 session 的调用顺序 `await`。多个协程并发操作同一实例会抛 `IllegalStateChangeError`。

```python
# ❌ 并发操作同一 session
groups, items, voices = await asyncio.gather(
    repo.list_groups(surface=surface),
    repo.list_active(surface=surface),
    voice_repo.list_active(),
)

# ✅ 顺序 await
groups = await repo.list_groups(surface=surface)
items = await repo.list_active(surface=surface)
voices = await voice_repo.list_active()
```

内存 SQLite 延迟极低，协程抢占 session 的 race window 几乎不开，pytest 全绿不等于这条安全。改过共享 session 的并发写法后，用带真实网络延迟的 PostgreSQL 验证。

同一请求里的 repo 方法多有 memo，第二次调用读内存，不产生额外往返。

## 事务边界

一个 HTTP 请求 = 一个 `AsyncSession` = 一个隐式事务。

- 依赖注入层在请求正常返回后 `commit()`，异常时 `rollback()`。
- 用例里 `flush()`，不在用例里 `commit()`。多次 flush 收成请求结束时的一次 commit，同一请求内多个仓储的写入是一个原子事务。
- 只在需要提前拿到生成的 id、或提前触发唯一约束校验时 `flush()`。其余交给依赖层收尾。

## Repository

接口用 `Protocol`。实现类显式继承该 Protocol，便于 IDE「Find All Implementations」。infrastructure import domain 的 Protocol，domain 不 import infrastructure。

```python
class IUserRepository(Protocol):
    async def save(self, user: User) -> User: ...
    async def find_by_id(self, user_id: str) -> User | None: ...
```

每条查询带软删过滤。ORM 不会自动加。漏掉 `deleted_at.is_(None)` 会把已删除行查回来，并且不抛异常。

```python
stmt = select(UserModel).where(
    UserModel.username == username,
    UserModel.deleted_at.is_(None),   # ← 漏了就静默返回已删数据
)
```

Save 用手写 upsert：

```python
async def save(self, entity: User) -> User:
    existing = await self._find_model_by_id(entity.id)
    if existing is None:
        self._session.add(UserModel.from_entity(entity))
    else:
        existing.name = entity.name          # 手动逐字段赋值
        existing.updated_at = entity.updated_at
    await self._session.flush()              # flush 不 commit，事务由上层控制
    return ...
```

`merge()` 不走这条路径。只 insert、不 update 的实体（session / event 日志）直接 `add` + `flush`，不写 existing 分支。

关联数据用 `find_by_ids(ids)` / `list_by_xxx_ids(ids)`。无外键，没有 relationship 可挂，`selectinload` / `joinedload` 用不上。用例先收集 id，再查一次。

```python
async def find_by_ids(self, ids: list[str]) -> list[Asset]:
    if not ids:                              # 空列表短路，别发一条 IN () 查询
        return []
    stmt = select(AssetModel).where(AssetModel.id.in_(ids), AssetModel.deleted_at.is_(None))
    return [r.to_entity() for r in (await self._session.execute(stmt)).scalars().all()]
```

分页返回 `tuple[list[Entity], int]`。count 与 data 分两条查询，默认 `created_at DESC`。

## ORM 模型与领域实体

ORM 基类提供 `id`（26 字符 ULID）、`created_at`、`updated_at`、`deleted_at`。主键默认 ULID，不用自增，也不用 UUID4：全局唯一且时间有序，索引局部性好，也不暴露业务量。

业务 ORM 模型直接或间接继承项目已有的公共 `BaseModel`。另建 `DeclarativeBase` 再只写 `metadata = BaseModel.metadata`，只共享元数据，不继承公共列和方法。审核时同时看继承链、公共列和对应迁移。

项目明确要求复用原业务主键时，在子类覆盖 `id` 的类型与生成规则，同时保留公共时间列和软删除。主键来自业务，仍然继承 `BaseModel`，不为同一行再造一个身份。与用户指令冲突、又无法判断能否偏离时先问，不自行豁免继承。

每个 ORM 模型实现 `to_entity()` 实例方法和 `from_entity()` 类方法。转换只发生在这两个方法里，上层拿到领域实体。

领域实体是纯 `@dataclass`，不依赖 ORM。状态转换做成方法（`mark_deleted()` / `touch()`）。有身份的实体、值对象、应用 DTO、外部事件输入各自怎么继承，见 `standard-fastapi-ddd-backend`。

值对象在构造时校验，不可变，实现 `__eq__` 与 `__hash__`，放 `domain/value_objects.py`：

```python
class Password:
    def __init__(self, plain: str) -> None:
        if not self._is_valid(plain):
            raise WeakPasswordException()      # 构造即校验，不存在"未校验的实例"
        self._plain = plain
```

## Schema

引用完整性在应用层维护。ORM 不用 `ForeignKey` / `ForeignKeyConstraint`。新迁移的 upgrade 目标同样不建物理外键。需要一致性时仍由应用层检查引用是否存在、归谁、处于什么业务状态，不把物理外键加回去。软删除和数据库级联冲突：外键级联会把已软删的子记录硬删掉。

跨表引用的类型与被引用主键一致。默认 ULID 用 `CHAR(26)`。复用业务 ID 时按项目约定，仍然不加外键。因为库不会兜引用，列注释写明指向哪张表。

验证时同时看 ORM metadata，以及在独立数据库执行 `alembic upgrade head` 之后的实际约束。只看模型，或只看测试通过，不能证明迁移结果没有外键。已部署的历史迁移按原文保留，用后续 revision 移除外键。还原旧版本的 downgrade 可以恢复旧约束，写明回滚前提。

索引：

| 类型 | 规则 |
|---|---|
| 软删索引 | 所有业务表为 `deleted_at` 建索引，加速「未删除记录」过滤 |
| 条件唯一索引 | 唯一约束带 `WHERE deleted_at IS NULL`，否则软删记录会挡住同名新记录 |
| 命名 | 普通 `idx_{table}_{cols}`、唯一 `uq_{table}_{cols}`；多列按高频查询顺序排 |

条件唯一索引用 `Index()` 声明时，两种方言的 where 都传：

```python
Index(
    "uq_users_email", "email", unique=True,
    postgresql_where=text("deleted_at IS NULL"),
    sqlite_where=text("deleted_at IS NULL"),   # ← 漏了它，测试库退化成全表唯一
)
```

只传 `postgresql_where` 时，SQLite 测试库会建成全表唯一索引。测试全绿，生产的部分唯一语义没有被测到。

新建表和列都写注释。

- 表注释写这个业务实体是什么。把表名换个说法不算注释。
- 列注释：枚举列出全部取值（`status: pending=待处理, running=进行中, done=已完成`）。没有外键的引用列写明指向哪张表（`关联 users.id，软删除 user 仍保留此引用`）。时间戳写业务语义（`首次播放完成时间，用于 7 日留存计算`）。
- 标准字段由基类统一注释，业务表不重复。
- 迁移里 `create_table` / `add_column` 同样带 `comment=`。列语义变了，注释一起改。

## 跨方言列类型

数据库专属类型（`ARRAY`、`JSONB` 等）测试要在别的方言上跑时，用 `TypeDecorator` 把分流关在类型内部。业务代码和 repository 里不写 `if dialect == "postgresql"`。

```python
class StringArray(TypeDecorator):
    """PG 上是 text[]，其余方言退化成 JSON list。"""
    impl = JSON              # fallback 类型
    cache_ok = True          # 类型实现无状态，可被语句缓存复用

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(String()))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        return list(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return list(value) if value is not None else []
```

`process_bind_param` / `process_result_value` 与方言无关，都转成同一个 Python 类型。

## Alembic 迁移

revision id 手动写成 `YYYYMMDD_NNNNNN_slug`，不用随机 hash。日期前缀让多个 worktree 各自编号。

revision id ≤ 32 字符。PostgreSQL 的 `alembic_version.version_num` 是 `varchar(32)`，超长插入失败。SQLite 不校验 varchar 长度，本地看不出来。

两条迁移链分叉时新建 merge revision，`down_revision` 传 tuple。

一个迁移只做一件事：

```
✅ 20260603_000001_add_async_tasks.py       创建一张表
✅ 20260610_000001_remove_foreign_keys.py   一个主题
❌ 20260612_000001_add_table_and_fix_index.py   混合不相关变更
```

Schema 变更（DDL）和数据迁移（DML）拆到不同 revision。数据迁移的文件名体现意图（`backfill_user_status`）。

`downgrade()` 要能在本地跑通 `alembic downgrade -1`，用来调试。不可逆的数据变更写 `raise NotImplementedError("不可逆")`。空 `pass` 会让 downgrade 假装成功，schema 和 version 表错位。

数据库专属类型或索引，给其它方言留 fallback：

```python
def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"

if _is_pg():
    op.execute("CREATE INDEX ... USING GIN (tags)")
else:
    op.create_index("idx_tags", "items", ["tags"])
```

`create_table` / `add_column` 本身不幂等。Alembic 靠 `alembic_version` 跟踪状态。数据迁移（seed / backfill）用 `ON CONFLICT DO NOTHING` 或等价写法，重跑可以过。

已经合入主干并部署的 revision 保持原文。要修正就新建后续 revision。

`--autogenerate` 只用来起草，逐行审。它认不出这些情况：列重命名（会生成 drop + add，数据丢掉）、索引和约束的非破坏性修改、数据迁移、服务端默认值、check 约束。

## 启动期自动迁移

非生产环境可以在启动时自动 `alembic upgrade head`，边界如下：

- 生产跳过。迁移是部署流水线里的独立步骤。启动期失败无法回滚，多实例一起启动还会抢迁移。
- 测试跳过。测试用 `Base.metadata.create_all` 建表，再跑 alembic 会和已建 schema 冲突。
- 其余环境自动迁移。失败抛异常，启动中止。
- `command.upgrade` 是同步 API，内部用 `asyncio.run`。已经有事件循环时，用 `asyncio.to_thread` 丢到线程池，避免嵌套 `asyncio.run`。
- 留一个环境变量可以跳过自动迁移。多个 worktree 共用一个远端库时，`alembic_version` 可能被别的分支推到本地不认识的 revision，自动迁移会卡住。

## SQLite 全绿不等于 PostgreSQL 全绿

SQLite 上通过的测试，到 PostgreSQL 上不一定成立。下面几条单测发现不了：

| 差异 | 后果 |
|---|---|
| 不校验 varchar 长度 | 超长 revision id / 字段值本地过、生产插入失败 |
| 不校验 CHECK 约束 | 存量脏数据打破约束，迁移在生产才炸 |
| 并发 race window 几乎不开 | 共享 session 的 `asyncio.gather` 本地测不出 |
| 只传 `postgresql_where` 时退化成全表唯一索引 | 唯一约束的真实语义没被测到 |
| 测试走 `create_all` 而非 alembic | 迁移文件本身从未被测试执行过 |

`create_all` 建得出表，不是迁移测试。drop 列、改 CHECK、改唯一约束、长标识符的迁移，要对一个真实 PostgreSQL 跑一次 `alembic upgrade head` 才算验证过。
