基于 poteto（Lauren Tan）的 [P Stack（pstack）](https://github.com/cursor/plugins/tree/main/pstack) 封装的个人工程规范插件。P Stack 提供工作流与行为原则，wstack 在此基础上补充领域规范，`skills/wayne-mode` 按 Playbook 决定用哪条规范。登录只在自行托管 cookie 会话时用 `standard-api-security-baseline`；Vercel 或 Supabase 登录不用它。其余规范仍是通用条款，项目路径不在本插件里。

质量门与验证从 [quality playbook](skills/wayne-mode/playbooks/quality.md) 进入。wstack 保存通用通过条件，项目保存检查命令和真实应用验证入口。行为按 poteto-mode。本插件不包含 pstack；会话里已有其 `SKILL.md` 就直接用，宣布没有之前先读已安装 pstack 插件里的 `skills/poteto-mode/SKILL.md`，只有读取失败才按 standard skill 继续。

## 安装与卸载

**先在当前客户端安装 P Stack，再安装 wstack。** 本插件不包含或自动安装 P Stack。

完整步骤见 [安装与卸载指南](install.MD)：包含 Claude Code、Codex、Cursor、Grok Build 的安装与卸载，以及其他兼容 Agent 的 Skills CLI 安装方法、个人与项目范围选择和卸载后检查。安装来源统一为 GitHub 仓库 `aidyfeng/wstack`。

## 技能

| skill | 何时用 |
| --- | --- |
| `standard-api-security-baseline` | Web/API 安全基线：会话、越权、CORS、密钥、限流、PII |
| `standard-celery-task-queue` | Celery worker：超时、重试、幂等、fork 后的数据库连接 |
| `standard-code-conventions` | Python + TypeScript 命名、风格、结构化日志 |
| `standard-dev-workflow` | 提交说明、bugfix 流程、pre-commit、评审 |
| `standard-fastapi-ddd-backend` | FastAPI + SQLAlchemy(async) + DDD 分层 |
| `standard-frontend-monorepo` | 前端 monorepo：站点、后台、小程序、App 与共享包 |
| `standard-graph-workflow-editor` | React Flow 图编辑器：草稿/发布与图校验 |
| `standard-llm-workflow-runtime` | LLM 工作流执行：state、节点注册、SSE |
| `standard-multi-provider-auth` | 大陆多渠道登录：手机号主身份、provider 抽象 |
| `standard-multitenant-isolation` | 多租户隔离：每条查询带租户过滤 |
| `standard-payment-integration` | 支付通道：幂等、回调验签、查单对账 |
| `standard-quality-gates` | lint、类型与构建检查、CI 门禁、行为证据与 pstack 依赖 |
| `standard-react-conventions` | 四端通用 React：状态、React Query、API 客户端 |
| `standard-react-native-app` | Expo 用户应用，含 iOS、Android 和网页版 |
| `standard-react-ops-console` | 运营后台 React SPA，与用户前端分开部署 |
| `standard-redis-patterns` | Redis：key 版本、失效、降级、幂等、测试隔离 |
| `standard-sqlalchemy-persistence` | SQLAlchemy 2.0 async：Repository、软删除、Alembic |
| `standard-taro-miniprogram` | Taro 微信小程序 |
| `standard-web-crawler` | 爬虫：去重、边界、robots、重试、增量 |
| `standard-websocket-realtime` | WebSocket：频道、心跳、重连、多进程广播 |

检查清单是否完整：`python3 scripts/check.py`。
