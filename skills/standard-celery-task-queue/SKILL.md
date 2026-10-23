---
name: standard-celery-task-queue
description: >
  Celery：任务需要独立 worker 时，改超时、重试、确认时机、fork 后的数据库引擎、asyncio.run
  桥接、chain()、队列路由或启动参数。
---

# Celery 独立 worker

只有工作需要独立 worker 时用 Celery。幂等的单进程任务用进程内调度器。

## App 配置

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

序列化用 JSON。pickle 能反序列化任意对象，broker 被攻破就是远程代码执行；JSON 还迫使参数是基础类型，避免把 ORM 对象当参数、fork 后复用连接（见「fork 安全」）。

`task_acks_late=True` 与 `task_reject_on_worker_lost=True` 一起用：执行完才确认，worker 崩溃时未确认的任务重新入队。执行到一半崩溃会把同一输入再跑一次，任务要幂等。

Broker 和 backend 用 Redis 时，用独立 DB 编号与业务缓存分开（如 `CELERY_REDIS_DB=1`）。共用 DB 会 key 冲突，清缓存时会清掉队列。

## 任务路由

```python
celery_app.conf.task_routes = {
    "src.celery_tasks.document_tasks.*": {"queue": "high"},
    "src.celery_tasks.website_tasks.*": {"queue": "high"},
    "worker.timeout_rollback": {"queue": "high"},
}
```

按模块设默认路由，同类任务共用一个队列。worker 用 `-Q` 只听指定队列，重任务和轻任务分到不同进程，慢任务堆积不会拖住另一批。

## 任务定义

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

`bind=True` 时第一个参数是任务实例，用 `self.retry(exc=e)` 做条件重试。这和 worker 崩溃后的重新入队不是同一条路径。

`max_retries=3` 写在装饰器上，配合 `self.retry()`。不写这个参数时，`self.retry()` 用 Celery 默认次数，看起来像限了 3 次，实际没有。

参数是 JSON 可序列化类型（字符串、数字、布尔、列表、dict）。ORM 实例、DB session、文件句柄要么序列化直接报错，要么丢掉状态。任务里用 ID 重新查询。

`asyncio.run()` 每次新建事件循环，跑完就销毁。同一个任务函数里不要嵌套 `asyncio.run()`，也不要复用上一次的循环。

## 长任务超时

```python
@celery_app.task(bind=True, max_retries=3, soft_time_limit=3600, time_limit=3660)
def crawl_website_task(self, ...):
    """网站爬取：软超时/硬超时按该任务实测设置，此处为占位值"""
```

装饰器上的 `soft_time_limit` / `time_limit` 覆盖 app 全局值。只放宽确认会跑很久的任务。把全局超时调大后，本该快速失败的任务也要等到这个更长的时限才被判为卡死。

## fork 安全

Celery 默认 prefork：子进程继承父进程 fork 那一刻的文件描述符，包括连接池里已经打开的 socket。多个子进程共用同一条 socket 时，查询和响应串在一起，出现协议错误，或读到别的进程的结果。现象随机，容易被看成数据库不稳定。

worker 引擎用 `NullPool`，并按 PID 重建：

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

`NullPool` 每次新建连接、用完关闭。worker 的任务频率远低于 Web 请求，这份开销换隔离。PID 变了就重建引擎，调用 `_get_task_engine()` 的地方拿到当前进程的实例，不用在启动钩子里另写「fork 后重连」。

这套只用于独立 worker。Web 多副本是各自 `create_app`，不 fork 出处理请求的子进程，不用 PID 检测。

## 任务里的数据库

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

任务走上面的 fork-safe 引擎，用独立的 session 入口。Web 请求的 session 工厂是另一套连接池，不能复用。

任务 session 不会在结束时自动提交，要调用 `session.commit()`。漏掉时任务显示成功，数据没有写入。异常由 `async with` rollback。

## 任务里的 Redis

发一条即忘的消息用同步客户端：

```python
import redis  # 同步客户端，不是 redis.asyncio

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
try:
    redis_client.publish(channel, json.dumps(message))
finally:
    redis_client.close()
```

异步客户端绑在创建它的事件循环上。`asyncio.run()` 每次都是新循环，在循环外复用异步客户端会打到已经关闭的循环上。

每次任务内新建同步客户端，用完 `close()`。模块级缓存的同步客户端会被 fork 出去的子进程共用，和数据库连接是同一类问题。

## chain()

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

`.s()` 是签名，`chain()` 按顺序执行。上一个任务的返回值是下一个任务的第一个位置参数。

每个任务返回 dict，带上下游要的全部字段。上下文字段全程透传：

```python
# parse → chunk
{"document_id": "...", "tenant_id": "...", "async_task_id": "...",
 "user_id": "...", "content_path": "...", "status": "parsed"}
# chunk → embed
{"document_id": "...", ..., "chunks": [...], "chunk_count": 10, "status": "chunked"}
```

`status` 标出当前阶段，失败时从日志看出卡在哪一步。返回值同样要能 JSON 序列化。`chunks` 这类自定义对象先转成 dict / list。

## 两类任务 ID

| 模型 | 用途 | ID |
|---|---|---|
| 业务态追踪实体（如 `AsyncTask`） | 前端任务面板、持久化状态、查历史 | 业务 ID（如 `async_task_id`） |
| Celery Task | 执行、重试、结果存储 | Celery 的 `task_id`（`AsyncResult.id`） |

```python
# 调用处：先创建业务态追踪实体 → 启动 pipeline → 把 Celery task_id 关联回业务实体
task = await create_task_use_case.execute(CreateTaskDTO(...))
celery_id = process_document_pipeline(..., async_task_id=task.id)
await task_repo.set_celery_task_id(task.id, celery_id)
```

`AsyncResult` 的寿命由 broker/backend 的过期策略决定，通常几小时到几天，不能当长期业务记录。业务实体保存「待处理 / 处理中 / 失败 / 完成」。

## Worker 启动

```bash
uv run python src/celery_worker.py                       # 默认：prefork, 4 并发, high 队列
uv run python src/celery_worker.py -c 2 -Q high,default   # 自定义并发数与监听队列
```

```python
celery_app.autodiscover_tasks(["src.celery_tasks"])
```

prefork 的每个子进程都会重建引擎，并各占一条数据库连接。`-c` 按数据库连接上限设定。`-Q` 决定听哪些队列，重任务队列可以单独用更低的并发。任务放在 `src/celery_tasks/`，用 `autodiscover_tasks` 注册，不在 app 里逐个 import。
