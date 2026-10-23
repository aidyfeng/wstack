---
name: wayne-mode
description: >-
  ZHIRONG 的工作方式。行为按当前会话的 poteto-mode，领域规范按 wstack 的 standard skill。
  用户提到 ZHIRONG、/wayne-mode，或要求按他的方式做事时使用。
  做登录、网页或 App、支付、多租户、用户编排的工作流、Celery、Redis、数据库建模、项目结构或质量门时也先读本技能，按 playbooks/ 选。
---

# wayne-mode

行为按当前会话里的 poteto-mode。本插件不包含 pstack。会话里看不见 poteto-mode，就说明，然后按下面的表继续。

适用性只在这里定。各 standard skill 只写做法。不要查 `project-map`，也不要读 `project-bindings.md`。

先读对应 Playbook，再打开它点名的技能。

| 任务 | 打开 |
| --- | --- |
| 登录、注册、会话、谁签发 token | [login](playbooks/login.md) |
| 网页、App、后台、小程序 | [frontend](playbooks/frontend.md) |
| 支付、订阅、回调、权益到账 | [payment](playbooks/payment.md) |
| SaaS 租户、组织、工作空间 | [tenancy](playbooks/tenancy.md) |
| 用户编排的工作流，含不接大模型的图 | [workflow](playbooks/workflow.md) |
| 异步任务、定时任务、独立 worker | [celery](playbooks/celery.md) |
| Redis 缓存、限流、幂等 | [redis](playbooks/redis.md) |
| 表、列、迁移、Repository | [persistence](playbooks/persistence.md) |
| 仓库目录、模块分层、包边界 | [structure](playbooks/structure.md) |
| lint、类型检查、CI 门禁、验证范围与交付证据 | [quality](playbooks/quality.md) |
| WebSocket 频道、心跳、多进程广播 | `standard-websocket-realtime` |
| 爬虫 | `standard-web-crawler` |
| 提交说明、pre-commit、评审 | `standard-dev-workflow` |
| Python / TypeScript 命名与日志 | `standard-code-conventions` |

## 优先

两边对同一步都有说法时按这里。

验证的产物和通过条件以 `standard-quality-gates` 为准，从 [quality](playbooks/quality.md) 进入。取得证据的步骤用该标准点名的 pstack 技能。

目录、命名、日志和包边界以上表点名的 standard skill 为准。规范没写到的决定，用 poteto-mode 里已经读过的原则。规范要求的层保留。

提交说明、bugfix 步骤、pre-commit 的覆盖和评审分级以 `standard-dev-workflow` 为准。提交前用 pstack 的 `deslop`。评审前用 `no-comments`。PR 正文用 `technical-writing`。
