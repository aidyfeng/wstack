---
name: wayne-mode
description: >-
  ZHIRONG 的工作方式。行为按当前会话的 poteto-mode，领域规范按 wstack 的 standard skill。
  用户提到 ZHIRONG、/wayne-mode，或要求按他的方式做事时使用。
  做登录、网页或 App、支付、多租户、用户编排的工作流、Celery、Redis、数据库建模、项目结构、质量门，或拆分大任务、多模型并行开发、worktree 协同、跨模型对抗审查时也先读本技能，按 playbooks/ 选。
---

# wayne-mode

`wayne-mode` 是叠在 `poteto-mode` 之上的领域与工程规范层，两层同时生效，不是二选一。`poteto-mode` 负责通用行为原则、回复风格与工作流骨架，本插件负责领域规范、质量门、提交评审与多 Agent 编排。本插件不包含 pstack。

## 1. 先加载底层 poteto-mode

1. 会话上下文里已有 `poteto-mode` 的 `SKILL.md` 时，直接沿用。
2. 否则，在当前客户端已安装的 pstack 插件或 skills 目录中查找并读取 `poteto-mode/SKILL.md`（不限于与 `setup-pstack` 严格同级），读到后作为底层行为规范启用。
3. 只有确认查找和读取都失败，才说明当前会话没有 `poteto-mode`，降级为仅按本插件规范继续。

## 2. 始终按本表叠加领域规范

无论底层 `poteto-mode` 是否可用，都要先查下表。命中任务就先读对应 Playbook，再打开它点名的 `standard-*` 技能，把约束叠加到当前任务上。适用性只在这里定，各 standard skill 只写做法。

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
| 拆分大任务、多模型并行开发、worktree 协同、跨模型对抗审查 | [orchestration](playbooks/orchestration.md) |
| WebSocket 频道、心跳、多进程广播 | `standard-websocket-realtime` |
| 爬虫 | `standard-web-crawler` |
| 提交说明、pre-commit、评审 | `standard-dev-workflow` |
| Python / TypeScript 命名与日志 | `standard-code-conventions` |

## 优先

通用工作方式与原则按底层 `poteto-mode`，领域规范与工程门禁按本插件；两者叠加执行，仅对同一步有冲突时按这里仲裁。

验证的产物和通过条件以 `standard-quality-gates` 为准，从 [quality](playbooks/quality.md) 进入。取得证据的步骤用该标准点名的 pstack 技能。

目录、命名、日志和包边界以上表点名的 standard skill 为准。规范没写到的决定，用 poteto-mode 里已经读过的原则。规范要求的层保留。

提交说明、bugfix 步骤、pre-commit 的覆盖和评审分级以 `standard-dev-workflow` 为准。提交前用 pstack 的 `deslop`。评审前用 `no-comments`。PR 正文用 `technical-writing`。

多任务垂直拆分、worktree 拓扑、跨家族模型路由和对抗审查门禁以 `standard-multi-agent-delivery` 为准，从 [orchestration](playbooks/orchestration.md) 进入。对应环节的具体执行手法优先用该标准点名的 pstack 技能。
