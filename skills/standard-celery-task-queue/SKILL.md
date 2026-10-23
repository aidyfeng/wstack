---
name: standard-celery-task-queue
description: >
  Celery 独立 worker 任务队列规范——任务装饰器参数（超时/重试/幂等）、fork 安全的数据库
  连接管理、同步 worker 里桥接 async 代码、chain() 任务链结果传递、队列路由与启动参数。
  做后台异步任务、长耗时流水线、需要独立进程横向扩容的重任务时使用。
  最容易踩的：prefork 子进程会继承父进程的数据库连接池，多个子进程共用同一 socket 会互相
  污染并报协议错误——必须 NullPool + PID 检测逐进程重建引擎。
  轻量幂等单实例场景优先用进程内调度器，不必为此引入独立 broker。
---

# Celery 独立 worker 任务队列规范

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

- 任务量大到需要独立进程 / 机器横向扩容，或需要重试、限流、优先级队列等 Celery 提供的
  调度语义
- 轻量、幂等、单实例场景优先用进程内调度器（如 APScheduler），不必为此引入独立 broker
  与 worker 进程

---

## App 配置：序列化、超时、确认时机三个易错项

```python
celery_app = Celery("worker", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_BROKER_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_soft_time_limit=300,        # 软超时：占位值，按任务实测调整
    task_time_limit=600,             # 硬超时：占位值，通常取软超时的 1.5~2 倍
    task_acks_late=True,             # 执行完成后再确认
    task_reject_on_worker_lost=True, # worker 崩溃时重新入队
)
```

- **只用 JSON 序列化**，不用 pickle——pickle 能反序列化任意对象，broker 一旦被攻破就是
  远程代码执行风险；JSON 序列化还强制任务参数必须是基础类型，间接防住"传个 ORM 对象
  当参数"这种会导致 fork 后连接复用的错误用法（见下文「fork 安全」）
- `task_acks_late=True` + `task_reject_on_worker_lost=True` 是一对：前者让任务**执行完
  才确认**（而不是取出队列就确认），后者让 worker 意外崩溃时未确认的任务重新入队。二者
  结合的代价是**任务必须幂等**——worker 在任务执行到一半崩溃，同一个任务会被重新执行
  一次，任务内部要能安全地处理"同一份输入执行两次"
- Broker 与 backend 常用 Redis，但要用**独立的 DB 编号**与业务缓存分开（如
  `CELERY_REDIS_DB=1`），避免 key 空间冲突、避免清缓存时误清掉任务队列

---

## 任务路由：按模块分队列，不要让重任务挤占轻任务

```python
celery_app.conf.task_routes = {
    "src.celery_tasks.document_tasks.*": {"queue": "high"},
    "src.celery_tasks.website_tasks.*": {"queue": "high"},
    "worker.timeout_rollback": {"queue": "high"},
}
```

按任务模块设默认路由，同类任务共享同一队列；worker 启动时可以只监听指定队列（见下文
「Worker 启动」），从而做到"重任务专用 worker、轻任务专用 worker"的物理隔离，一批慢
任务堆积不会拖慢另一批任务的响应。

---

## 任务定义模式：bind=True + 幂等重试 + JSON 可序列化 + async 桥接

```python
@celery_app.task(bind=True, max_retries=3)
def parse_document_task(
    self,                          # bind=True 让任务函数接收 self，可调用 self.retry()
    document_id: str,
    tenant_id: str,
    async_task_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    return asyncio.run(_parse())   # async → sync 桥接
```

- `bind=True`：任务函数第一个参数是任务实例本身，用于显式调用 `self.retry(exc=e)` 做
  条件重试（区别于 worker 崩溃触发的被动重入队）
- `max_retries=3`：主动重试的上限次数，配合 `self.retry()` 使用；不写这个装饰器参数时
  `self.retry()` 会用 Celery 默认值，容易踩到"以为限了 3 次实际没限"
- **所有参数必须是 JSON 可序列化类型**（字符串 / 数字 / 布尔 / 列表 / dict），不能传
  ORM 实例、DB session、文件句柄等有状态对象——这类对象要么无法序列化直接报错，要么
  序列化后丢失状态，任务里必须用 ID 重新查询
- `asyncio.run()` 是最简单的 async → sync 桥接：每次调用创建一个全新事件循环、跑完
  即销毁。**不要在同一个任务函数里嵌套调用 `asyncio.run()`**，也不要试图复用上一次
  调用创建的循环——`asyncio.run()` 的设计前提就是"一次性、跑完就扔"

---

## 长任务需要单独覆盖超时，不要放大全局值

```python
@celery_app.task(bind=True, max_retries=3, soft_time_limit=3600, time_limit=3660)
def crawl_website_task(self, ...):
    """网站爬取：软超时/硬超时按该任务实测设置，此处为占位值"""
```

装饰器级别的 `soft_time_limit` / `time_limit` 会覆盖 app 全局配置。**只对确认会长时间
运行的任务单独放宽**，不要为了省事把全局超时调大——全局超时调大意味着所有任务（包括本该
快速失败的任务）都要等到这个更长的时限才会被判定为卡死，故障发现会变慢。

---

## fork 安全：NullPool + PID 检测重建数据库引擎

**这是独立 worker 场景最容易踩、也最难在开发环境复现的坑。** Celery 默认用 prefork
（多进程）模式：主进程 fork 出多个子进程处理任务，子进程会**继承父进程 fork 那一刻已经
建立好的所有文件描述符**，包括数据库连接池里已经打开的 socket。多个子进程共用同一个
底层 socket 会导致：不同进程的查询和响应在同一条连接上互相串扰，出现莫名其妙的协议
错误或读到别的进程查询的结果——现象随机、难以稳定复现，容易被误判成"数据库不稳定"。

解法是给 worker 进程用的引擎设置 `NullPool`（禁用连接池，每次操作都开新连接、用完立即
关闭）+ 按 PID 检测重建：

```python
_task_engine: AsyncEngine | None = None
_task_engine_pid: int | None = None
_task_engine_lock = Lock()

def _get_task_engine() -> AsyncEngine:
    global _task_engine, _task_engine_pid
    current_pid = os.getpid()

    with _task_engine_lock:
        if _task_engine is None or _task_engine_pid != current_pid:
            # fork 检测：PID 变化说明当前是刚 fork 出来的子进程，必须重建引擎
            _task_engine = create_async_engine(
                settings.DATABASE_URL,
                poolclass=NullPool,  # 关键：不用连接池，避免连接被跨进程共享
            )
            _task_engine_pid = current_pid

    return _task_engine
```

- `NullPool` 用连接创建开销换取隔离性——独立 worker 场景任务频率通常远低于 Web 请求，
  这个开销可接受
- PID 检测让**同一个引擎对象在 fork 前后被自动识破并重建**，不需要在 worker 启动钩子
  里手写"fork 后重连"的逻辑，任何调用 `_get_task_engine()` 的地方都能拿到进程正确的
  实例
- 这条规则**只对独立 worker 场景成立**。Web 服务进程不 fork 出处理请求的子进程（多副本
  是独立进程各自 `create_app`，不是 fork），不需要这套 PID 检测

---

## 任务里用数据库：专用 session 入口 + 手动 commit

```python
@celery_app.task(bind=True, max_retries=3)
def my_task(self, document_id: str) -> dict[str, Any]:
    return asyncio.run(_do_work())

async def _do_work():
    async with get_task_session_context() as session:  # 走上面的 fork-safe 引擎
        repo = SqlAlchemyDocumentRepository(session)
        doc = await repo.find_by_id(document_id)
        doc.start_parsing()
        await repo.save(doc)
        await session.commit()  # 必须手动提交，不会自动 commit
```

- Worker 任务必须用**独立的 session 入口**（走上文 fork-safe 引擎），不能复用 Web
  请求路径的 session 工厂——两者的连接池策略必须不同
- **必须手动调用 `session.commit()`**，任务 session 默认不像某些 Web 中间件那样在
  请求结束时自动提交；漏写 commit 是最容易造成"任务显示成功但数据没写进去"的原因
- 异常时 session 走 `async with` 上下文管理器自动 rollback，不需要手写 try/except 包
  提交逻辑

---

## 任务里用 Redis：同步客户端，不能复用异步客户端

```python
import redis  # 同步客户端，不是 redis.asyncio

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
try:
    redis_client.publish(channel, json.dumps(message))
finally:
    redis_client.close()
```

- 任务体本身在 `asyncio.run()` 内部跑，但如果只是发一条 fire-and-forget 的消息（如
  发布一条通知），用同步 Redis 客户端更简单，不需要为此再包一层协程
- 不能在 `asyncio.run()` 之外持有一个跨调用复用的异步 Redis 客户端——异步客户端绑定
  创建它时所在的事件循环，而 `asyncio.run()` 每次调用都是全新循环，跨调用复用会绑定
  到已经关闭的循环上报错
- 每次任务内新建客户端、用完立即 `close()`，不要在模块级缓存一个"全局"同步 Redis
  客户端指望跨任务复用——fork 安全的顾虑同样适用于任何跨进程共享的连接对象

---

## chain() 任务链与结果传递格式

```python
from celery import chain

def process_document_pipeline(
    document_id: str,
    tenant_id: str,
    async_task_id: str | None = None,
    user_id: str | None = None,
) -> str:
    pipeline = chain(
        parse_document_task.s(document_id, tenant_id, async_task_id, user_id),
        chunk_document_task.s(),    # 接收上一步返回值作为第一个参数
        embed_document_task.s(),
        bm25_index_task.s(),
    )
    result = pipeline.apply_async()
    return result.id
```

- `.s()` 创建任务签名（signature），`chain()` 把多个签名串成顺序执行的管道；**上一个
  任务的返回值会自动作为下一个任务的第一个位置参数**，不需要手写胶水代码传递
- 每个任务返回一个 dict，必须包含下游任务所需的全部字段——上下文字段（各种 ID）要
  **全程透传**，不能中途丢：

  ```python
  # parse → chunk
  {"document_id": "...", "tenant_id": "...", "async_task_id": "...",
   "user_id": "...", "content_path": "...", "status": "parsed"}
  # chunk → embed
  {"document_id": "...", ..., "chunks": [...], "chunk_count": 10, "status": "chunked"}
  ```

- 返回值里放一个 `status` 字段标识当前阶段完成状态，便于任务失败时从日志判断卡在
  哪一步
- 链上所有返回值必须 JSON 可序列化（与任务参数同样的约束）——`chunks` 这类中间产物
  如果是自定义对象，要先转成 dict / list 再放进返回值

---

## 双重任务模型：业务态追踪实体与 Celery Task ID 分离

一个 pipeline 通常同时关联两个不同层面的"任务"概念，不要把两者混为一谈：

| 模型 | 用途 | ID 关联 |
|---|---|---|
| 业务态追踪实体（数据库表，如 `AsyncTask`） | 给前端 UI 展示任务面板、持久化状态、支持
  查询历史 | 业务自定义 ID（如 `async_task_id`） |
| Celery Task | 实际异步执行、Celery 自己的重试/结果存储 | Celery 生成的 `task_id`
  （`AsyncResult.id`） |

```python
# 调用处：先创建业务态追踪实体 → 启动 pipeline → 把 Celery task_id 关联回业务实体
task = await create_task_use_case.execute(CreateTaskDTO(...))
celery_id = process_document_pipeline(..., async_task_id=task.id)
await task_repo.set_celery_task_id(task.id, celery_id)
```

原因：Celery 的 `AsyncResult` 生命周期由 broker/backend 的过期策略控制（通常几小时到
几天），不适合当作长期可查询的业务记录；业务态实体是持久化的、可以承载业务语义的状态
机（如"待处理/处理中/失败/完成"），两者分层职责清楚才不会互相牵制。

---

## Worker 启动参数与任务自动发现

```bash
uv run python src/celery_worker.py                       # 默认：prefork, 4 并发, high 队列
uv run python src/celery_worker.py -c 2 -Q high,default   # 自定义并发数与监听队列
```

```python
celery_app.autodiscover_tasks(["src.celery_tasks"])
```

- 并发数（`-c`）不是越大越好——prefork 模式下每个并发子进程都会走一遍上文「fork 安全」
  的引擎重建，也各自占用独立的数据库连接，并发数要结合数据库连接上限设置
- `-Q` 指定 worker 监听哪些队列，配合前文「任务路由」实现物理隔离：重任务队列可以单独
  起一组并发更低但资源更宽裕的 worker
- 任务模块放在统一目录（如 `src/celery_tasks/`）下，通过 `autodiscover_tasks` 自动
  注册，不需要在 app 里手工 import 每一个任务模块

---
