---
name: standard-fastapi-ddd-backend
description: >
  FastAPI + SQLAlchemy(async) + DDD 分层后端规范。改业务模块、领域实体、Repository、UseCase、
  路由、Pydantic schema、异常码、依赖注入、lifespan、定时任务时使用。
  收录的多是**静默失败**——编译器、测试、线上告警三道全拦不住的那类：部分更新判据用错会清空
  老客户端的字段（model_fields_set），shutdown 等待用错 API 会让进程零响应却仍在 LISTEN
  （asyncio.wait 而非 wait_for）。
  前提：四层分层 + Protocol Repository + 统一响应信封；Django/Flask 或贫血分层不适用。
---

# FastAPI + DDD 分层后端规范

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

适用前提（不满足则本规范部分条目不成立）：

- FastAPI，Pydantic v2，SQLAlchemy 2.0 async
- 业务模块按 `domain/` `application/` `infrastructure/` `presentation/` 分层
- Repository 接口用 `Protocol` 定义在 application 层，实现在 infrastructure 层
- 所有响应走统一信封（`code`/`data`/`message`）

数据库、缓存、测试、安全另有专门规范，本篇只管后端应用层。

本篇多数条目防的是**静默失败**：编译器不报、测试不红、线上不告警，只是数据悄悄错了或进程
悄悄卡了。它们值得成文正是因为常规三道防线全拦不住——凡标了「静默」的地方，都不能指望
"出问题会有人发现"，只能靠写的时候就不犯。

---

## ★★ 红线 1：PATCH 部分更新——"没传这个键" vs "显式传 null"

区分这两者**必须**用 `payload.model_fields_set`，不能用 `is not None`。

**触发条件**：字段的合法值域本身包含 `None` 作为一个有意义的取值时。典型是"继承上级配置"
"回退默认值""不覆盖"这类语义的可空字段。此时：

- 请求体**没带**这个键 → 应该沿用原值（老客户端根本不知道有这个字段）
- 请求体**显式传 `null`** → 应该写入 `None`（用户主动选择"继承/清空"）

两种情况下 `payload.field` 都是 `None`。用 `is not None` 判断，"没传 → 沿用原值"这条分支
**永远走不到**。

**后果**：老客户端一保存就把该字段静默清空。不抛异常、不进日志、不触发告警——只是数据没了。
Repository 的 `save()` 若是整行覆盖，风险更高：漏一个字段就是清空，而不是报错。

```python
# ✅ 值域含 None（None = "继承上级配置"）→ 只能判断键在不在
if "theme_mode" in payload.model_fields_set:
    body["theme_mode"] = payload.theme_mode

# ✅ 值域不含 None（None 就等价于"没传"）→ is not None 够用
#    注意区分：显式传 [] 是"清空列表"，与 None（未传）是两回事
if payload.tags is not None:
    body["tags"] = payload.tags
```

**判断口诀**：新加一个可为 `None` 的 PATCH 字段前先问——这个字段的合法值域里，`None` 本身
是不是一个有意义的目标状态？是 → 必须用 `model_fields_set`。

**测试要求**：这条只有**真实 HTTP 层测试**测得出。单测直接构造 Pydantic model 传 dict 不会
复现"请求体缺键"场景（`model_fields_set` 是反序列化请求体时才填充的运行期状态）。必须写两个
用例：不带该字段 / 显式传 `null`，分别断言。

---

## ★★ 红线 2：等待任务必须用 `asyncio.wait`，不是 `asyncio.wait_for`

lifespan shutdown（以及任何"等一个可能卡住的清理任务"的场景）都要有超时上界，且用
`asyncio.wait(timeout=)`。

**为什么不能用 `wait_for`**：`wait_for` 超时后会 cancel 任务并**继续等**它把取消走完。任务若
正卡在 `finally` 里的一次网络 await 上（连接半开、对端不响应），`wait_for` 自己也一起挂住——
超时形同虚设。`asyncio.wait` 到点即返回，不管任务有没有真正结束。

**事故形态**：某个后台消费者的清理卡在一条半开的连接上永不返回 → shutdown 完不成 → 服务进程
关不掉。而 reload/多进程模式下 LISTEN socket 由父进程持有，于是**端口照常 LISTEN、TCP 握手照常
成功**，所有请求连得上却永远等不到响应，全程零报错——从外部看像"服务活着但全部超时"，极难定位。

```python
# ✅ 到点即返回，不等 cancellation
async def _await_bounded(task: asyncio.Task, timeout: float, step: str, logger) -> None:
    _, pending = await asyncio.wait({task}, timeout=timeout)
    if pending:
        logger.warning("shutdown_step_timeout", step=step, timeout_seconds=timeout)
```

- 每一步清理（后台 task、连接池……）都套一层
- 超时值走配置项，不要写死数字
- **例外**：不涉及"`finally` 里挂起网络调用"的叶子清理（如单次 `aclose()`），用
  `wait_for` + `contextlib.suppress` 反而更合适——它能真正取消掉

**启动期资源探针一律 warn-only**：缓存 ping、对象存储连通性、后台消费者启动失败都只
`logger.warning`，不阻断应用启动——它们是运行时可恢复依赖，不是启动前置条件。生产环境的
硬性检查应当独立成一个显式的启动检查函数。

---

## 模块分层

每个业务模块固定四层：`domain/` `application/` `infrastructure/` `presentation/`。

**用例位置固定为 `application/use_cases/`**，不能直接散放在 `application/` 根目录。
DTO 与 `ports/` 保留在 application 层；新增或移动用例时同步更新导出与调用方 import。
四层目录齐全不代表用例位置合规，评审应核对实际文件路径。

**这四层不是流水线的四段，是整洁架构的四个同心圆**：

```
Frameworks & Drivers    FastAPI / SQLAlchemy / Redis 本身
└─ Interface Adapters   presentation/（Controller + Presenter） ＋ infrastructure/（Gateway）
   └─ Use Cases         application/
      └─ Entities       domain/
```

`presentation/` 与 `infrastructure/` **是同一圈的两半**，地位对等、互不认识、都可替换：前者把
HTTP 请求翻译成用例入参、把用例结果翻译成响应体；后者把用例声明的 Protocol 翻译成 SQL。两者
都在用例外面，都不许被内层 import。

把四层读成"请求依次穿过的四段"是最常见的误读，且不会报错——只会让业务判断堆在 router 里、
ORM 类型漏进 application 签名。等到要换 Web 框架或换存储，成本已经悄悄回到重写级别。

**依赖规则落到 import 上**（本节唯一可机械检查的部分）：

| 这一层 | 允许 import | 禁止 import |
|---|---|---|
| `domain/` | 标准库、共享内核、异常基类模块 | 其余全部，含本模块 application；**尤其是配置模块** |
| `application/` | 本模块 domain、本模块 `ports/`、其它模块的 application DTO | 任何 `infrastructure/`、任何 `presentation/`、Web 框架 |
| `infrastructure/` | 本模块 domain、本模块 application `ports/` | 任何 `presentation/` |
| `presentation/` | 本模块 application / domain、其它模块的 `presentation/dependencies` | `infrastructure/`（`dependencies.py` 除外，见下） |

「共享内核」指跨模块复用、且**不含业务语义**的技术设施：ID 生成、时间工具、实体基类。配置模块
不属于它——配置是部署期输入，领域规则依赖它就等于把环境差异写进了业务，该值应由调用方传入。

**跨边界只传简单数据结构**：ORM Model 不出 `infrastructure/`，Pydantic schema 不进
`application/`，用例的入参出参一律是 dataclass DTO。这条是上表能成立的前提——破了它，import
方向再对也没用。

**`domain/entities.py`——纯 dataclass，不依赖 ORM**

具有独立身份与生命周期的领域实体必须继承项目共享内核中已有的 `BaseEntity`，
复用身份、时间戳和软删除能力，不在业务模块另建同名基类或只复制字段。
领域实体不继承 ORM 的 `BaseModel`，两种基类职责不同。

无独立身份的值对象、应用 DTO、外部事件输入不要求继承 `BaseEntity`；
不能仅因使用 `@dataclass` 或 `frozen=True` 就将业务实体视为 DTO。
如需复用既有业务 ID，应核对基类的 id 类型与生成规则，并在 ORM 双向转换中保持同一身份，
不能为满足继承而静默生成第二个身份。确需偏离时说明原因并核实用户已有授权，
没有授权且无法判断时先询问，再记录到项目绑定。

❌ 领域实体里不得出现 `Mapped[...]` / `mapped_column` 等 ORM 类型。

**`domain/` 装的不只是实体——业务规则本身也在这一圈**

除 `entities.py` / `exceptions.py` 外，domain 下还应有：

- `value_objects.py`：`@dataclass(frozen=True)` 的值对象，构造时自校验
- **领域规则模块**：纯函数 ＋ 常量 ＋ frozen dataclass 返回值，零 I/O、零 session、零 `await`，
  不建 DB 也能直接单测

```python
# domain/tiering.py —— 规则的正确形态
TIER_THRESHOLDS: dict[int, int] = {...}

@dataclass(frozen=True)
class TierResult:
    new_tier: int
    promoted: bool

def apply_progress(tier: int, current: int, delta: int) -> TierResult: ...
```

**判据——一条规则该放 domain 还是 use case**：换一个用例，这条规则还成立吗？

- 成立 → domain。档位阈值、金额换算、状态机迁移的合法性、聚合内的不变量校验都属此类
- 只在这一次编排里成立 → use case。"先查 A、没有就建 B、然后发通知"是编排，不是规则

误判方向几乎总是同一个：规则被写进 `execute()` 里。这不报错，只是在第二个用例需要同一条规则时
被复制一份，然后两份各自演化。**一个模块的 domain 下只有 `entities.py`，通常不是它简单，而是
规则都漏到用例里了。**

**`infrastructure/models.py`——ORM Model 必须双向转换**

每个 ORM Model 同时实现 `to_entity()` 与 `from_entity()`。ORM ↔ 领域实体的转换**只在这两个
方法内**发生；application / presentation 层不得直接持有 ORM Model。

**`application/ports/repositories.py`——Protocol，`I` 前缀**

```python
class IXxxRepository(Protocol):
    async def save(self, entity: Xxx) -> Xxx: ...
    async def find_by_id(self, id: str) -> Xxx | None: ...
```

infrastructure 层的 `SqlAlchemyXxxRepository` 实现该 Protocol，**不需显式继承**（结构化子类型）。
这样 application 层不必 import infrastructure，依赖方向始终向内。

**`presentation/`——三类文件，职责不可互串**

| 文件 | 整洁架构角色 | 干什么 | 红线 |
|---|---|---|---|
| `router.py` | Controller | 解析入参 → 调 UseCase → 映射成 response schema → 装信封 | 不含业务判断 |
| `schemas.py` | 边界 DTO ＋ Presenter | 请求/响应 Pydantic 模型，用例结果到响应体的转换 | 不进 application |
| `dependencies.py` | Composition Root | 组装依赖图 | 不含业务逻辑 |

**Composition Root 例外**：`dependencies.py` 必须 import 具体实现类（`SqlAlchemyXxxRepository`、
对象存储的某个云厂商实现），这是全模块唯一合法的向外 import——依赖倒置总得有人知道实现是谁，
那个人就是它。**`router.py` 不在此列**：它只该认识 UseCase 与 schema。

router 里出现 `from ...infrastructure...` 就是装配逻辑内联进了 Controller。不会当场出错，代价
是换实现时要改的地方从 1 处变成 N 处。

**注入标注写 Protocol，不写具体类**：

```python
# ✅ Controller 只需要知道能力
repo: Annotated[IXxxRepository, Depends(get_xxx_repository)]
# ❌ 具体类写进 router 签名 —— 类型上就把 Controller 钉死在 SQLAlchemy 上
repo: Annotated[SqlAlchemyXxxRepository, Depends(get_xxx_repository)]
```

**Presenter 转换收进 schema 的 classmethod**，router 只留一行。用例返回 DTO 用
`from_result()`，直接来自实体用 `from_entity()`：

```python
async def get_xxx_feed(
    use_case: Annotated[ListXxxFeedUseCase, Depends(get_list_xxx_feed_use_case)],
) -> ApiResponse[XxxFeedResponse]:
    result = await use_case.execute(scope)
    return success_response(data=XxxFeedResponse.from_result(result))
```

❌ 在 router 函数体里手工逐字段拼 `XxxResponse(...)`——那是 Presenter 的活，散在 Controller 里
就没法单独测，也没法被第二个端点复用。

**router 是 Humble Object**：函数体里每多一个 `if`，就多一行只能靠 HTTP 测试覆盖的逻辑。判据是
这个 `if` 换成 gRPC 入口还要不要——要 → 挪进 UseCase；只为 HTTP 服务（如从会话里取出调用者
身份、领域异常到 404 的映射）→ 留下。

**拆分判据——何时从一个 `router.py` 拆成多个**

默认一个模块一个 `router.py`。出现下面任一条时按**子域**拆：

- 单文件超过约 15 个端点或约 500 行
- 文件内出现互不相干的两组资源，各有各的 schema 与鉴权要求
- 某组端点只在其中一个入口注册（多入口单体见下一节）

拆出的文件名 `{子域}_router.py`，schema 同步拆成 `{子域}_schemas.py`，各自在
`register_xxx_routers()` 里 `include_router`。

❌ 不要拆成"一个端点一个文件"。用例粒度已经由 `application/use_cases/` 承担了（一个用例一个
文件），presentation 再切一刀只会让一次改动横跨更多文件，而这两层的变更几乎总是同时发生。

**没有依赖图要组装的模块可以没有 `dependencies.py`**——只有一两个端点、且复用别的模块的工厂时，
直接 import 那个模块的 `presentation/dependencies` 即可，不要为凑齐三件套建空文件。

**例外：简单模块可以少层。** 没有独立路由、只被其它模块调用的模块，可以只有三层（无
`presentation/`）。不要为凑齐四层造空目录——空目录比少一层更误导。

---

## 多入口单体

同一个应用工厂函数 `create_app(include_x_routers=..., include_y_routers=...)` 服务多个入口
（如面向用户的 API 与管理后台各一个进程）。入口文件**只做参数选择**：

```python
# entry_app.py
app = create_app(include_app_routers=True, include_admin_routers=False)
# entry_admin.py
app = create_app(include_app_routers=False, include_admin_routers=True)
```

- ✅ 新路由归到 `register_app_routers()` / `register_admin_routers()` 之一
- ❌ 不要在各入口文件里分别写 `add_middleware` / 异常处理器 / 健康检查——必须是同一份中间件栈、
  同一套异常处理，否则两个入口的行为会悄悄分叉，且分叉后极难发现
- 确实需要"只在某一入口跑"的逻辑（如某个只有一侧才需要的后台消费者），一律通过 lifespan
  构造函数的参数分叉，不要在入口文件里写逻辑

---

## UseCase 与依赖注入

类名 `XxxUseCase`，**单一**公共方法 `async def execute(...)`，依赖构造函数注入。需要另一个
操作就新建一个类——不要在同一个类里加第二个公共方法。

**入参**：单个 ID 或一两个标量直接裸传；4 个以上的可选筛选字段必须打包成 DTO——列表查询用
`ListXxxQuery`，写操作用 `XxxCommand`。裸堆参数的代价是加一个字段要改所有调用点，DTO 只改一处。

**注入**：每个模块在 `presentation/dependencies.py` 定义工厂函数，逐层 `Depends()` 串起依赖图，
每层工厂只负责组装自己这一层：

```python
async def get_xxx_use_case(
    repo: Annotated[SqlAlchemyXxxRepository, Depends(get_xxx_repository)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
) -> XxxUseCase:
    return XxxUseCase(repo, storage)
```

**鉴权位置**：强制鉴权用 router 级 `dependencies=[Depends(get_admin_user)]`，不占路由函数的
参数位。只有**允许匿名访问**时才把鉴权依赖放进函数参数，且必须带默认值 `= None`——因此它只能
排在参数列表最后。这是 Python 语法约束（无默认值参数不能排在有默认值参数之后），不是风格偏好。

---

## 响应信封

所有响应走统一泛型信封，客户端只认 `code`：

```python
class ApiResponse(BaseModel, Generic[T]):
    code: int = 0                 # 固定 0 表示成功，不可变更
    message: str = "success"
    data: T | None = None
    meta: PageMeta | None = None  # 仅分页接口
    trace_id: str | None = None   # 由中间件/上下文自动注入
```

- 普通响应走 `success_response(data=...)`，分页走 `paginated_response(...)`，
  `meta` 含 `total_pages = ceil(total / page_size)`
- 非分页接口 `meta` 为 `None`
- ❌ 不要绕过信封直接 `return {...}`——客户端的成功判断是统一的 `code === 0`，绕过就等于
  给客户端加一条特例分支
- 流式响应（SSE / StreamingResponse）天然在信封之外，若项目有此类端点需单独约定并在此注明

---

## 请求校验

所有 Pydantic 请求/响应模型必须 `model_config = ConfigDict(extra="forbid")`。

这**不是** Pydantic 的默认值（默认 `extra="ignore"`），是显式加固：未知字段直接 422，而不是被
静默吞掉。静默吞掉的典型后果是客户端改了字段名、服务端毫无反应，双方都以为生效了。

```python
class CreateXxxRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=50)
```

- 所有字段用 `Field()` 声明约束，不要裸类型注解
- 查询参数用 `Annotated` + `Query()`，且带 `description`：
  `page: Annotated[int, Query(default=1, ge=1, description="页码")]`
- 枚举取值用 `Literal[...]`，不要用 `str` 再手工校验
- 部分更新的字段判断见**红线 1**

---

## 异常与错误码

按语义分层，每层一个码段，业务码与 HTTP 状态码**相互独立**：

```
BaseAppException
├── SystemException           1000  HTTP 500
│   └── DatabaseException     1100
├── ValidationException       2000  HTTP 400
├── AuthException             3000  HTTP 401
├── ResourceNotFoundException 4000  HTTP 404
├── ExternalServiceException  5000  HTTP 502
└── BusinessException         6000  HTTP 400
```

基类极少直接抛；各模块在自己的 `domain/exceptions.py` 定义子类并覆盖 `default_code`：

```python
class XxxNotFoundException(ResourceNotFoundException):
    default_code = 4520
    default_message = "xxx not found"
```

- 不覆盖 `default_message` / `default_http_status` 则沿用父类
- `details` 只在 debug 开启时透出，**生产环境恒为 `None`**——它可能含内部结构信息
- `trace_id` 必须包含，用于日志关联
- ❌ 业务代码不要裸抛 `HTTPException`：框架原生异常只有兜底映射，抛出来就丢失了业务码，
  客户端拿不到可判别的错误类型

---

## 定时任务：先做选型，再谈写法

**选型判据**（决定用哪种，不要默认跟随过往项目习惯）：

| | 进程内调度（APScheduler 等） | 独立 worker（Celery / RQ / Arq 等） |
|---|---|---|
| 适合 | 低频维护型任务（清理、对账、快照），单实例或可幂等重跑 | 高吞吐、需重试与死信、任务要横向扩容、耗时长会拖住进程 |
| 代价 | 多实例部署时会**重复执行**，需自行加分布式锁或只在单一实例启用 | 多一套 broker + worker 进程要运维、要监控、要处理 fork 安全 |

选进程内调度的前提是：任务轻、幂等、且你清楚多实例下的重复执行问题。一旦需要重试语义、任务队列
或独立扩容，就该上独立 worker——**这时本节的写法不适用，改用对应 worker 框架的规范**。

**选了进程内调度时的写法**：

```python
scheduler = AsyncIOScheduler(timezone="UTC")
scheduler.add_job(
    cleanup_old_events, trigger="cron", hour=3, minute=0,
    id="cleanup_events", replace_existing=True,   # id + replace 防重复注册
)
scheduler.start()
```

- 用配置项控制启停（默认开），关掉时整个 scheduler 不起——本地开发和测试环境通常要关
- 任务函数**自己开 session、自己 commit**，不依赖请求生命周期（没有请求上下文可用）
- 启动失败 warn-only，不阻断应用启动
- 关闭用 `shutdown(wait=False)`，不等任务跑完——否则会拖慢 shutdown（见**红线 2**）
- 加新任务 = 加一条 `add_job`，不要新建第二个 scheduler 实例

---
