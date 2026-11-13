基于 poteto（Lauren Tan）的 [P Stack（pstack）](https://github.com/cursor/plugins/tree/main/pstack) 封装的个人工程规范插件。P Stack 提供工作流与行为原则，wstack 在此基础上补充领域规范，`skills/wayne-mode` 按 Playbook 决定用哪条规范。登录只在自行托管 cookie 会话时用 `standard-api-security-baseline`；Vercel 或 Supabase 登录不用它。其余规范仍是通用条款，项目路径不在本插件里。

质量门与验证从 [quality playbook](skills/wayne-mode/playbooks/quality.md) 进入。wstack 保存通用通过条件，项目保存检查命令和真实应用验证入口。行为按 poteto-mode。本插件不包含 pstack；会话里已有其 `SKILL.md` 就直接用，宣布没有之前先读已安装 pstack 插件里的 `skills/poteto-mode/SKILL.md`，只有读取失败才按 standard skill 继续。

## 安装与卸载

**先在当前客户端安装 P Stack，再安装 wstack。** 本插件不包含或自动安装 P Stack。

完整步骤见 [安装与卸载指南](install.MD)：包含 Claude Code、Codex、Cursor、Grok Build 的安装与卸载，以及其他兼容 Agent 的 Skills CLI 安装方法、个人与项目范围选择和卸载后检查。安装来源统一为 GitHub 仓库 `aidyfeng/wstack`。

## wayne-mode 自动启用

Claude Code 和 Codex 插件通过 `SessionStart` 默认开启 wayne-mode，直接注入 [SKILL.md](skills/wayne-mode/SKILL.md) 的实际正文；规则只维护这一份。恢复会话或压缩上下文后，按当前会话状态重新注入。需要 Python 3 在客户端的非交互环境 `PATH` 上，并允许插件运行 hook。

| 会话消息 | 效果 |
| --- | --- |
| `/wayne-mode on` | 当前会话开启 |
| `/wayne-mode off` | 当前会话关闭 |
| `/wayne-mode status` | 查看当前会话状态和新会话默认值 |
| `/wayne-mode default on` | 后续新会话默认开启，当前会话不变 |
| `/wayne-mode default off` | 后续新会话默认关闭，当前会话不变 |

Claude Code 插件使用 `/wstack:wayne-mode on` 等带命名空间的入口。Codex 的输入框会拦截未知斜杠命令，请在上述消息前加一个空格，作为普通消息发送；hook 会识别命令。这里只接受单独一行的控制消息，代码块、解释文字和夹带任务的消息不会改变状态。

Cursor、Grok Build 和仅用 Skills CLI 安装的客户端保留按需技能加载，不注册自动开关。客户端限制、状态路径、故障处理及卸载清理见[开关说明](install.MD#wayne-mode-自动启用与开关)。`off` 停止自动应用本插件规则，无法删除历史上下文，也不会关闭用户、项目或 P Stack 的独立规范。

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

检查技能清单：`python3 scripts/check.py`；检查开关行为：`python3 -m unittest discover -s scripts -p 'test_wayne_mode.py'`。
