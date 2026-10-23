---
name: wayne-mode
description: >
  决定这次任务用哪条 standard skill。拿不准适用性、做登录，或要分清官网、用户应用、后台、小程序时先读本技能，按 playbooks/ 选。
---

# wayne-mode

适用性只在这里定。各 standard skill 只写做法。不要查 `project-map`，也不要读 `project-bindings.md`。

有 Playbook 的任务先读那一篇，再打开它点名的技能。没有 Playbook 的任务直接打开表里的技能。

| 任务 | 打开 |
| --- | --- |
| 登录、注册、会话、谁签发 token | [login](playbooks/login.md) |
| 页面属于官网、用户应用、后台还是小程序 | [frontend](playbooks/frontend.md) |
| FastAPI 路由、用例、DDD 分层 | `standard-fastapi-ddd-backend` |
| SQLAlchemy、Repository、迁移、软删除 | `standard-sqlalchemy-persistence` |
| Redis key、缓存、限流、幂等 | `standard-redis-patterns` |
| Celery worker、独立进程任务 | `standard-celery-task-queue` |
| WebSocket 频道、心跳、多进程广播 | `standard-websocket-realtime` |
| 支付下单、回调验签、对账 | `standard-payment-integration` |
| 手机号主身份、多个登录渠道 | `standard-multi-provider-auth` |
| 多租户查询隔离 | `standard-multitenant-isolation` |
| LLM 工作流执行 | `standard-llm-workflow-runtime` |
| React Flow 图编辑器 | `standard-graph-workflow-editor` |
| 爬虫 | `standard-web-crawler` |
| 提交说明、pre-commit、评审 | `standard-dev-workflow` |
| Python / TypeScript 命名与日志 | `standard-code-conventions` |
