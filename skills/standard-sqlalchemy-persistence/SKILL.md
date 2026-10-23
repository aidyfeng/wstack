---
name: standard-sqlalchemy-persistence
description: >
  SQLAlchemy 2.0 async 持久层规范——Repository 模式、ORM 模型与领域实体转换、软删除、
  无外键设计、索引与注释约定、跨方言列类型、Alembic 迁移。写 repository、加表加列、
  建索引、写迁移、调事务边界时使用。
  多数条目防的是**静默失败**：漏加软删过滤会静默返回已删数据、条件唯一索引只传一种方言的
  where 会让测试库静默退化成全表唯一、共享 session 上用 asyncio.gather 会炸
  IllegalStateChangeError 但 SQLite 单测永远测不出来。
  贯穿全篇的前提：**测试库（SQLite）比生产库（PG）宽松，全绿不等于安全**。
  预设 async engine + Alembic + 领域实体与 ORM 模型分离。
---

# SQLAlchemy async 持久层

## 当前项目上下文

本 skill 是用户级通用规范，项目事实由当前工作仓库的 `project-map` 提供。

1. 以当前任务所在仓库／worktree 为根，先读 `AGENTS.md` 或 `CLAUDE.md` 中声明的项目地图。
   未声明时检查仓库内 `.claude/skills/project-map/SKILL.md` 或 `.agents/skills/project-map/SKILL.md`；
   不借用主工作树、其他项目或用户级目录中的项目地图。
2. 按本 skill 的完整名称查地图索引，只读相关绑定资料。绑定链接相对于地图所在目录解析，
   代码路径相对于当前仓库解析；地图声明不适用时，不为套用规范引入技术栈或改变架构。
3. 旧地图若仍把绑定放在仓库内的 `standard-*/references/project-bindings.md`，按地图声明读
   当前仓库的旧位置；不要在用户级 skill 目录寻找项目绑定。
4. 缺少地图或绑定时先说明缺口并核实当前代码；不编造项目事实，也不因此停止能完成的工作。
   只有关键事实无法核实时才询问。调用其他规范时同样先确认其适用范围与可用性。

用户明确指令优先。绑定中的选型、已知偏离和事故记录是项目上下文，不把旧实现自动提升为
通用规则，也不把已记录的偏离自动当作 bug 修复；有冲突时说明影响，再按已授权范围处理。

---

适用前提：

- SQLAlchemy 2.0 async（`AsyncSession`）+ Alembic
- 领域实体（纯 dataclass）与 ORM 模型分离，靠双向转换方法衔接
- Repository 接口用 `Protocol` 定义在 application/domain 层
- 生产 PostgreSQL、测试可能跑 SQLite

本篇多数条目防的是**静默失败**：不抛异常、不留日志，只是查出了不该查的数据、或约束根本没生效。
另有一条贯穿全篇的前提——**测试库比生产库宽松**，见文末专节。

---

## ★★ 红线：共享 session 上禁止 `asyncio.gather`

同一请求内所有 repository 共享同一个 `AsyncSession`。`AsyncSession` **不允许多个协程并发操作
同一实例**，会抛 `IllegalStateChangeError`。

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

**SQLite 单测测不出这个。** 内存 SQLite 延迟极低，协程抢占 session 的 race window 几乎不会
打开，pytest 全绿不代表安全；只有连了真实网络延迟的 PG 才稳定触发。改动共享 session 的并发
写法后必须用真 PG 验证。

**顺序 await 通常不比并发慢**——repo 方法多有按请求缓存的 memo，第二次调用直接读内存，不产生
额外往返。不要为了"看起来并行"引入这个风险。

---

## Session 生命周期与事务边界

**一个 HTTP 请求 = 一个 `AsyncSession` = 一个隐式事务。**

- 依赖注入层在请求正常返回后统一 `commit()`，异常时 `rollback()`
- **用例内部不手动 `commit()`**，只 `flush()`——把多次 flush 换成单次最终 commit，保证同一
  请求内多个仓储的写入是一个原子事务
- 只在需要提前拿到生成的 id、或提前触发唯一约束校验时才 `flush()`，其余交给依赖层收尾

---

## Repository 模式

**接口用 `Protocol`（结构化子类型），不用 ABC。** 实现类显式继承该 Protocol，好处是 IDE 能
"Find All Implementations"。依赖方向：infrastructure import domain 的 Protocol，反过来不行。

```python
class IUserRepository(Protocol):
    async def save(self, user: User) -> User: ...
    async def find_by_id(self, user_id: str) -> User | None: ...
```

**每条查询必须显式带软删过滤。** ORM 层没有自动过滤，全靠手写：

```python
stmt = select(UserModel).where(
    UserModel.username == username,
    UserModel.deleted_at.is_(None),   # ← 漏了就静默返回已删数据
)
```

**Save 走手写 upsert，不用 `merge()`：**

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

**仅追加型实体（session / event 日志，只 insert 不 update）省略 existing 判断**，直接 `add` +
`flush`。为不会更新的实体写 upsert 分支是多余的。

**关联数据用批量方法，不用 `selectinload` / `joinedload`。** 无外键设计下没有 relationship 可
挂载，关联数据走 `find_by_ids(ids)` / `list_by_xxx_ids(ids)`，由 use case 先收集 id 再一次
查询——这是本架构下防 N+1 的标准手段：

```python
async def find_by_ids(self, ids: list[str]) -> list[Asset]:
    if not ids:                              # 空列表短路，别发一条 IN () 查询
        return []
    stmt = select(AssetModel).where(AssetModel.id.in_(ids), AssetModel.deleted_at.is_(None))
    return [r.to_entity() for r in (await self._session.execute(stmt)).scalars().all()]
```

**分页返回 `tuple[list[Entity], int]`**，count 与 data 分两条查询，默认 `created_at DESC`。

---

## ORM 模型与领域实体

**ORM 基类**统一提供 `id`（26 字符 ULID）/ `created_at` / `updated_at` / `deleted_at`。ULID 而非
自增或 UUID4：全局唯一**且时间有序**，索引局部性好，且不暴露业务量。

**所有业务 ORM 模型必须直接或间接继承项目已有的公共 `BaseModel`。**
另建 `DeclarativeBase` 后仅赋值 `metadata = BaseModel.metadata` 只共享元数据，
不会继承公共列与方法，不能视为复用了基类。审核时同时确认继承链、公共列及对应迁移。

默认使用上述 ULID；项目明确要求复用原业务主键时，可在子类覆盖 `id` 的类型与生成规则，
同时保留公共时间列和软删除能力。主键值来自业务不等于可以绕过基类，也不应自动再造一个身份。
存在冲突时先核对用户指令与项目绑定；无法判断则询问，不自行豁免继承要求。

**每个 ORM 模型必须实现双向转换**——`to_entity()` 实例方法、`from_entity()` 类方法。转换只在
这两个方法内发生，上层拿到的永远是领域实体，不是 ORM 对象。

**领域实体是纯 `@dataclass`**，无 ORM 依赖，状态转换封装成方法（`mark_deleted()` / `touch()`）。
有身份与生命周期的实体复用项目已有 `BaseEntity`，与 ORM 的 `BaseModel` 分开继承；
值对象、应用 DTO 和外部事件输入不套用实体继承要求。具体边界见 `standard-fastapi-ddd-backend`。

**值对象**在构造时即校验、不可变、实现 `__eq__` 与 `__hash__`，放 `domain/value_objects.py`：

```python
class Password:
    def __init__(self, plain: str) -> None:
        if not self._is_valid(plain):
            raise WeakPasswordException()      # 构造即校验，不存在"未校验的实例"
        self._plain = plain
```

---

## Schema 约定

**无外键设计。** 禁用数据库外键与级联删除，引用完整性在应用层维护：

- ORM 禁用 `ForeignKey` / `ForeignKeyConstraint`，新增迁移的升级目标同样不得建立物理 FK。
  引用存在性、归属和业务状态由应用层检查，不能因为需要一致性就自行加回数据库外键。
- 软删除与级联删除天然冲突——FK 级联会把已软删的子记录硬删掉
- 跨表引用的类型与被引用主键保持一致；默认 ULID 用 `CHAR(26)`，复用业务 ID 时按项目约定，
  不加 FK 约束
- 代价是引用完整性无人兜底，所以列注释必须写明"指向哪张表"（见下）

验证时同时检查 ORM metadata 与在独立数据库执行 `alembic upgrade head` 后的实际约束；
只检查模型或只看测试通过，不能证明迁移结果无外键。已部署的历史迁移按原文保留，
用后续 revision 移除外键；还原旧版本的 downgrade 可以恢复旧约束，须说明回滚前提。

**索引：**

| 类型 | 规则 |
|---|---|
| 软删索引 | 所有业务表为 `deleted_at` 建索引，加速"未删除记录"过滤 |
| 条件唯一索引 | 唯一约束一律带 `WHERE deleted_at IS NULL`，否则软删记录会挡住同名新记录 |
| 命名 | 普通 `idx_{table}_{cols}`、唯一 `uq_{table}_{cols}`；多列按高频查询顺序排 |

条件唯一索引用 ORM `Index()` 声明时，**必须同时传两种方言的 where**：

```python
Index(
    "uq_users_email", "email", unique=True,
    postgresql_where=text("deleted_at IS NULL"),
    sqlite_where=text("deleted_at IS NULL"),   # ← 漏了它，测试库退化成全表唯一
)
```

只传 `postgresql_where` 时 SQLite 测试库会建成**全表唯一索引**，测不出真实语义——测试全绿，
生产行为却不同。

**注释是 schema 的一等公民，新建表和列必须写。**

- 表注释：一句话说明业务实体，不抄表名
- 列注释：枚举字段**列全取值**（`status: pending=待处理, running=进行中, done=已完成`）；
  无 FK 的引用列**说明指向哪张表**（`关联 users.id，软删除 user 仍保留此引用`）；时间戳写业务
  语义而非"创建时间"这种废话（`首次播放完成时间，用于 7 日留存计算`）
- 标准字段由基类统一注释，业务表不重复
- 迁移里 `create_table` / `add_column` 同样带 `comment=`；列语义变化时同步更新注释

---

## 跨方言列类型

需要数据库专属类型（`ARRAY`、`JSONB`…）但测试跑别的方言时，用 `TypeDecorator` 封装，把分流
关在类型内部——业务代码和 repository 里不该出现 `if dialect == "postgresql"`：

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

`process_bind_param` / `process_result_value` 与方言无关，统一转成同一个 Python 类型，让上层
调用方感觉不到底层差异。

---

## Alembic 迁移

**revision id 用日期前缀 `YYYYMMDD_NNNNNN_slug`**，手动指定、不用随机 hash。日期前缀让多个
worktree/分支并行开发时各自建号，不必协调"谁占下一个序号"。

**revision id 必须 ≤32 字符**——PG 的 `alembic_version.version_num` 是 `varchar(32)`，超长直接
插入失败。而 SQLite 不校验 varchar 长度，本地测不出来。

两条迁移链分叉时新建 merge revision，`down_revision` 传 tuple。

**一个迁移只做一件事：**

```
✅ 20260603_000001_add_async_tasks.py       创建一张表
✅ 20260610_000001_remove_foreign_keys.py   一个主题
❌ 20260612_000001_add_table_and_fix_index.py   混合不相关变更
```

Schema 变更（DDL）与数据迁移（DML）拆到不同 revision，数据迁移的文件名体现意图
（`backfill_user_status`）。

**`downgrade()` 必须可用**——即便生产不回滚，本地 `alembic downgrade -1` 要能跑通用于调试。
不可逆的数据变更显式 `raise NotImplementedError("不可逆")`，而不是留空 `pass`（留空会让
downgrade 假装成功，schema 与 version 表就此错位）。

**方言感知**：数据库专属类型/索引必须为其它方言提供 fallback：

```python
def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"

if _is_pg():
    op.execute("CREATE INDEX ... USING GIN (tags)")
else:
    op.create_index("idx_tags", "items", ["tags"])
```

**幂等**：`create_table` / `add_column` 本身不幂等（Alembic 靠 `alembic_version` 跟踪状态，
这是设计预期）。但数据迁移（seed / backfill）要用 `ON CONFLICT DO NOTHING` 等价语法容忍重试。

**已合入主干并部署的 revision 禁止修改内容**，需要修正就新建后续 revision 打补丁。

**`--autogenerate` 只用于起草，必须逐行人工审核。** 它识别不了：列重命名（会生成 drop + add，
**丢数据**）、索引/约束的非破坏性修改、数据迁移、服务端默认值与 check 约束。

---

## 启动期自动迁移

非生产环境可在应用启动时自动 `alembic upgrade head`，但要划清边界：

- **生产环境显式跳过**——迁移是部署流水线的独立步骤。启动期跑迁移失败无法回滚，且多实例
  并发启动会产生 migrate 竞争
- **测试环境跳过**——测试用 `Base.metadata.create_all` 直接建表，跑 alembic 反而与已建 schema 冲突
- 其余环境自动迁移，**失败直接抛异常阻断启动**，不静默降级
- Alembic 的 `command.upgrade` 是同步 API，内部用 `asyncio.run`。在已有事件循环里直接调会
  嵌套 `asyncio.run` 报错，必须 `asyncio.to_thread` 扔线程池
- 留一个**逃生舱环境变量**跳过自动迁移：多个 worktree 共享同一个远端库时，`alembic_version`
  可能被别的分支推到本地未知的 revision，自动迁移会卡住

---

## 测试库比生产库宽松

贯穿全篇的前提。SQLite 上跑绿的测试，在 PG 上未必成立——**以下几条都无法靠单测发现**：

| 差异 | 后果 |
|---|---|
| 不校验 varchar 长度 | 超长 revision id / 字段值本地过、生产插入失败 |
| 不校验 CHECK 约束 | 存量脏数据打破约束，迁移在生产才炸 |
| 并发 race window 几乎不开 | 共享 session 的 `asyncio.gather` 本地测不出 |
| 只传 `postgresql_where` 时退化成全表唯一索引 | 唯一约束的真实语义没被测到 |
| 测试走 `create_all` 而非 alembic | **迁移文件本身从未被测试执行过** |

推论：涉及 drop 列、改 CHECK、改唯一约束、长标识符的迁移，必须对一个真实 PG 跑一次
`alembic upgrade head` 才算验证通过。

---
