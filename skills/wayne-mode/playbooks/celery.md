# 异步任务

任务要独立进程或独立机器扩容，或要用重试、限流、优先级队列时，读 `standard-celery-task-queue`。

幂等、单进程就够的定时任务用进程内调度器，规则在 `standard-fastapi-ddd-backend` 的定时任务一节。不为这种任务加 broker 和 worker。

worker 的数据库连接按 Celery 技能处理（fork 之后按进程重建）。Web 请求的 session 不拿去给 worker 用。
