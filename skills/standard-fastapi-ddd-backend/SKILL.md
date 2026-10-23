---
name: standard-fastapi-ddd-backend
description: >
  FastAPI：改 DDD 分层、UseCase、路由、schema、异常码或依赖注入时使用。PATCH 可空字段、
  lifespan 里等待任务、进程内定时任务也用本技能。
---

# FastAPI + DDD 分层

## 红线：PATCH 部分更新

字段的合法值里 `None` 本身有意义时（继承上级配置、回退默认、不覆盖），用 `payload.model_fields_set` 区分「没传这个键」和「显式传 null」。两种情况下 `payload.field` 都是 `None`。用 `is not None` 时，「没传 → 沿用原值」走不到。

没带这个键：沿用原值（老客户端不知道有这个字段）。显式 `null`：写入 `None`。

老客户端一保存就会把该字段清空，不抛异常、不进日志。Repository 的 `save()` 若整行覆盖，漏一个字段就是清空，不是报错。

```python
# 值域含 None（None = "继承上级配置"）→ 只能判断键在不在
if "theme_mode" in payload.model_fields_set:
    body["theme_mode"] = payload.theme_mode

# 值域不含 None（None 就等价于"没传"）→ is not None 够用
# 显式传 [] 是"清空列表"，与 None（未传）是两回事
if payload.tags is not None:
    body["tags"] = payload.tags
```

新加可为 `None` 的 PATCH 字段时先问：`None` 是不是一个有意义的目标状态？是，就用 `model_fields_set`。值域不含 `None` 时 `is not None` 够用。显式 `[]` 是清空列表，与未传不同。

这条要用真实 HTTP 测试。直接构造 Pydantic model 传 dict 不会复现「请求体缺键」——`model_fields_set` 在反序列化请求体时才填。写两个用例：不带该字段，以及显式传 `null`，分别断言。

## 红线：等待任务用 asyncio.wait

lifespan shutdown，以及任何要等一个可能卡住的清理任务的地方，用 `asyncio.wait(timeout=)`，到点即返回。

`asyncio.wait_for` 超时后会 cancel 任务，然后继续等取消走完。任务若卡在 `finally` 里的一次网络 await（连接半开、对端不响应），`wait_for` 自己也挂住，超时等于没有。

后台消费者的清理卡在半开连接上时，shutdown 完不成，进程关不掉。reload / 多进程模式下 LISTEN socket 在父进程，端口仍在 LISTEN，TCP 握手成功，请求永远等不到响应，全程没有报错。

```python
# 到点即返回，不等 cancellation
async def _await_bounded(task: asyncio.Task, timeout: float, step: str, logger) -> None:
    _, pending = await asyncio.wait({task}, timeout=timeout)
    if pending:
        logger.warning("shutdown_step_timeout", step=step, timeout_seconds=timeout)
```

每一步清理（后台 task、连接池）都套一层。超时值走配置，不写死数字。

不涉及「`finally` 里挂起网络调用」的叶子清理（如单次 `aclose()`）用 `wait_for` 加 `contextlib.suppress`，这样能真正取消掉。

启动期资源探针只 `logger.warning`，不阻断启动：缓存 ping、对象存储连通性、后台消费者启动失败。它们是运行时可恢复的依赖。生产环境的硬性检查做成单独的启动检查函数。

## 模块分层

每个业务模块四层：`domain/`、`application/`、`infrastructure/`、`presentation/`。

用例放在 `application/use_cases/`，不散放在 `application/` 根目录。DTO 和 `ports/` 留在 application 层。新增或移动用例时同步更新导出和调用方 import。四层目录齐全不等于用例位置对了，评审核对实际文件路径。

这四层是同心圆，不是请求依次穿过的四段：

```
Frameworks & Drivers    FastAPI / SQLAlchemy / Redis 本身
└─ Interface Adapters   presentation/（Controller + Presenter） ＋ infrastructure/（Gateway）
   └─ Use Cases         application/
      └─ Entities       domain/
```

`presentation/` 与 `infrastructure/` 同圈，互不 import，都在用例外面，都可以替换。前者把 HTTP 翻译成用例入参、把结果翻译成响应；后者把 Protocol 翻译成 SQL。读成流水线时，业务判断会堆在 router 里，ORM 类型会漏进 application 的签名。

| 这一层 | 允许 import | 禁止 import |
|---|---|---|
| `domain/` | 标准库、共享内核、异常基类模块 | 其余全部，含本模块 application；尤其是配置模块 |
| `application/` | 本模块 domain、本模块 `ports/`、其它模块的 application DTO | 任何 `infrastructure/`、任何 `presentation/`、Web 框架 |
| `infrastructure/` | 本模块 domain、本模块 application `ports/` | 任何 `presentation/` |
| `presentation/` | 本模块 application / domain、其它模块的 `presentation/dependencies` | `infrastructure/`（`dependencies.py` 除外，见下） |

共享内核是跨模块复用、且不含业务语义的技术设施：ID 生成、时间工具、实体基类。配置不是共享内核。配置是部署期输入，领域规则依赖它就把环境差异写进了业务；该值由调用方传入。

跨边界只传 dataclass DTO。ORM Model 不出 `infrastructure/`，Pydantic schema 不进 `application/`。import 方向对了，类型漏过边界仍然破层。

### 领域

`domain/entities.py` 是纯 dataclass，不出现 `Mapped[...]` / `mapped_column`。

有独立身份和生命周期的实体继承项目共享内核里已有的 `BaseEntity`，复用身份、时间戳和软删除。不在业务模块另建同名基类，也不只复制字段。领域实体不继承 ORM 的 `BaseModel`。

值对象、应用 DTO、外部事件输入不继承 `BaseEntity`。不能因为 `@dataclass` 或 `frozen=True` 就把业务实体当成 DTO。复用既有业务 ID 时，核对基类的 id 类型和生成规则，ORM 双向转换保持同一个身份。为了满足继承再生成第二个身份，这条实体就有了两个 ID。

除 `entities.py` / `exceptions.py` 外，domain 还包括：

- `value_objects.py`：`@dataclass(frozen=True)`，构造时自校验
- 领域规则模块：纯函数、常量、frozen dataclass 返回值，零 I/O、零 session、零 `await`，不建 DB 也能单测

```python
# domain/tiering.py —— 规则的正确形态
TIER_THRESHOLDS: dict[int, int] = {...}

@dataclass(frozen=True)
class TierResult:
    new_tier: int
    promoted: bool

def apply_progress(tier: int, current: int, delta: int) -> TierResult: ...
```

换一个用例这条规则还成立，就放 domain：档位阈值、金额换算、状态机迁移是否合法、聚合内的不变量。只在这一次编排里成立，就放 use case：「先查 A、没有就建 B、然后发通知」是编排。

规则写进 `execute()` 后，第二个用例会复制一份，然后两份各自演化。一个模块的 domain 下只有 `entities.py`，通常是规则漏到用例里了。

### 端口与 ORM 边界

```python
class IXxxRepository(Protocol):
    async def save(self, entity: Xxx) -> Xxx: ...
    async def find_by_id(self, id: str) -> Xxx | None: ...
```

`SqlAlchemyXxxRepository` 实现该 Protocol。实现类是否显式继承见 `standard-sqlalchemy-persistence`。application 不 import infrastructure。

每个 ORM Model 实现 `to_entity()` 和 `from_entity()`。转换只发生在这两个方法里。application / presentation 不持有 ORM Model。

### presentation

| 文件 | 角色 | 做什么 | 边界 |
|---|---|---|---|
| `router.py` | Controller | 解析入参，调 UseCase，映射成 response schema，装信封 | 不含业务判断 |
| `schemas.py` | 边界 DTO 与 Presenter | 请求/响应 Pydantic 模型，用例结果到响应体的转换 | 不进 application |
| `dependencies.py` | Composition Root | 组装依赖图 | 不含业务逻辑 |

`dependencies.py` 是全模块唯一合法的向外 import：它要认识 `SqlAlchemyXxxRepository` 和对象存储的具体实现。`router.py` 只认识 UseCase 和 schema。router 里出现 `from ...infrastructure...` 就是把装配写进了 Controller，换实现时要改的地方从 1 处变成 N 处。

注入标注写 Protocol：

```python
# Controller 只需要知道能力
repo: Annotated[IXxxRepository, Depends(get_xxx_repository)]
# 具体类写进 router 签名，类型上就把 Controller 钉死在 SQLAlchemy 上
repo: Annotated[SqlAlchemyXxxRepository, Depends(get_xxx_repository)]
```

Presenter 转换放在 schema 的 classmethod 上，router 留一行。用例返回 DTO 用 `from_result()`，直接来自实体用 `from_entity()`：

```python
async def get_xxx_feed(
    use_case: Annotated[ListXxxFeedUseCase, Depends(get_list_xxx_feed_use_case)],
) -> ApiResponse[XxxFeedResponse]:
    result = await use_case.execute(scope)
    return success_response(data=XxxFeedResponse.from_result(result))
```

在 router 函数体里逐字段拼 `XxxResponse(...)` 时，这段转换没法单独测，第二个端点也复用不了。

router 函数体里的 `if` 只能靠 HTTP 测试覆盖。这个 `if` 换成 gRPC 入口还要，就挪进 UseCase。只为 HTTP 服务的留下：从会话取出调用者身份、领域异常映射成 404。

默认一个模块一个 `router.py`。出现任一条时按子域拆：单文件超过约 15 个端点或约 500 行；文件里有互不相干的两组资源，各有 schema 和鉴权；某组端点只在其中一个入口注册（见「多入口单体」）。

拆出的文件名 `{子域}_router.py`，schema 同步拆成 `{子域}_schemas.py`，在 `register_xxx_routers()` 里 `include_router`。用例已经是 `application/use_cases/` 里一个文件一个用例。presentation 再拆成一个端点一个文件，一次改动会横跨更多文件，而这两层几乎总是一起改。

没有依赖图要组装时可以没有 `dependencies.py`。只有一两个端点、且复用别的模块的工厂时，直接 import 那个模块的 `presentation/dependencies`。

没有独立路由、只被其它模块调用的模块可以没有 `presentation/`。不为凑齐四层建空目录。

## 多入口单体

同一个 `create_app(...)` 服务多个入口。入口文件只做参数选择：

```python
# entry_app.py
app = create_app(include_app_routers=True, include_admin_routers=False)
# entry_admin.py
app = create_app(include_app_routers=False, include_admin_routers=True)
```

新路由归到 `register_app_routers()` 或 `register_admin_routers()` 之一。中间件、异常处理器、健康检查只写一份。各入口文件分别 `add_middleware` 时，两边的行为会分叉，而且分叉后很难发现。

只在某一入口跑的逻辑（某一侧才需要的后台消费者）通过 lifespan 构造函数的参数分叉，不在入口文件里写逻辑。

## UseCase 与依赖注入

类名 `XxxUseCase`，唯一的公共方法是 `async def execute(...)`，依赖从构造函数注入。另一个操作就新建一个类。

单个 ID 或一两个标量直接传。4 个以上的可选筛选字段打包成 DTO：列表查询用 `ListXxxQuery`，写操作用 `XxxCommand`。裸堆参数时，加一个字段要改所有调用点。

每个模块在 `presentation/dependencies.py` 写工厂，用 `Depends()` 串起依赖图，每层工厂只组装自己这一层：

```python
async def get_xxx_use_case(
    repo: Annotated[SqlAlchemyXxxRepository, Depends(get_xxx_repository)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
) -> XxxUseCase:
    return XxxUseCase(repo, storage)
```

强制鉴权用 router 级 `dependencies=[Depends(get_admin_user)]`，不占路由函数的参数位。允许匿名访问时，鉴权依赖放进函数参数并带默认值 `= None`，因此它排在参数列表最后。无默认值的参数不能排在有默认值的参数后面，这是 Python 语法。

## 响应信封

客户端只认 `code`：

```python
class ApiResponse(BaseModel, Generic[T]):
    code: int = 0                 # 固定 0 表示成功，不可变更
    message: str = "success"
    data: T | None = None
    meta: PageMeta | None = None  # 仅分页接口
    trace_id: str | None = None   # 由中间件/上下文自动注入
```

普通响应用 `success_response(data=...)`，分页用 `paginated_response(...)`。`meta` 含 `total_pages = ceil(total / page_size)`。非分页接口的 `meta` 是 `None`。

直接 `return {...}` 会绕过信封。客户端的成功判断是统一的 `code === 0`，绕过就给客户端加一条特例。流式响应（SSE / `StreamingResponse`）不走信封，单独约定。

## 请求校验

请求和响应模型用 Pydantic v2，并且：

```python
class CreateXxxRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=50)
```

`extra="forbid"` 不是默认值（默认 `extra="ignore"`）。未知字段返回 422。默认忽略时，客户端改了字段名，服务端没有反应，双方都以为生效了。

字段用 `Field()` 写约束。查询参数用 `Annotated` 加 `Query()`，并带 `description`：`page: Annotated[int, Query(default=1, ge=1, description="页码")]`。枚举取值用 `Literal[...]`。部分更新见上面的 PATCH 红线。

## 异常与错误码

业务码与 HTTP 状态码分开：

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

基类很少直接抛。各模块在 `domain/exceptions.py` 定义子类并覆盖 `default_code`：

```python
class XxxNotFoundException(ResourceNotFoundException):
    default_code = 4520
    default_message = "xxx not found"
```

不覆盖 `default_message` / `default_http_status` 就沿用父类。`details` 只在 debug 开启时透出，生产环境恒为 `None`，它可能含内部结构。响应带 `trace_id`，用来关联日志。

业务代码抛领域异常子类。裸抛 `HTTPException` 会走到框架的兜底映射，业务码丢失，客户端拿不到可判别的错误类型。

## 定时任务

| | 进程内调度（APScheduler 等） | 独立 worker（Celery / RQ / Arq 等） |
|---|---|---|
| 适合 | 低频维护（清理、对账、快照），单实例，或可以幂等重跑 | 高吞吐、要重试和死信、要横向扩容、耗时会拖住进程 |
| 代价 | 多实例会重复执行，自行加分布式锁，或只在单一实例启用 | 多一套 broker 和 worker |

需要独立 worker 时用 `standard-celery-task-queue`，下面的写法不适用。进程内任务要轻、要幂等，并且处理多实例重复执行：分布式锁，或只在一个实例启用。

选了进程内调度时：

```python
scheduler = AsyncIOScheduler(timezone="UTC")
scheduler.add_job(
    cleanup_old_events, trigger="cron", hour=3, minute=0,
    id="cleanup_events", replace_existing=True,   # id + replace 防重复注册
)
scheduler.start()
```

用配置项控制启停，默认开。关掉时整个 scheduler 不起。本地开发和测试通常关掉。

任务函数自己开 session、自己 `commit()`。这里没有请求上下文。启动失败只 `logger.warning`，不阻断应用启动。关闭用 `shutdown(wait=False)`，不等任务跑完，否则会拖住 shutdown（见上面的 `asyncio.wait` 红线）。新任务加一条 `add_job`，不新建第二个 scheduler。
