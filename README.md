# wstack

个人工程规范，打成一个插件。`skills/wayne-mode` 按 Playbook 决定用哪条规范。登录只在自行托管 cookie 会话时用 `standard-api-security-baseline`；Vercel 或 Supabase 登录不用它。其余规范仍是通用条款，项目路径不在本插件里。

改规范只改这个仓库里的 `skills/`。`~/.agents/skills/standard-*` 是装插件之前的副本，两边会分叉。

质量门与验证从 [quality playbook](skills/wayne-mode/playbooks/quality.md) 进入。wstack 保存通用通过条件，项目保存检查命令和真实应用验证入口。行为按 poteto-mode。pstack 未随本插件安装。会话里已有其 SKILL.md 就直接用；宣布没有之前，先读已安装 pstack 插件里的 `skills/poteto-mode/SKILL.md`。只有读取失败才说明没有，并按 standard skill 继续。质量门里的官方链接仍是参考，调用前确认技能可用。

## 安装

把下面的路径换成这个仓库的路径，或换成推上去之后的 `owner/repo`。个人安装对所有项目生效；项目安装只对那一个仓库生效。

### Claude Code

```bash
# 个人
claude plugin marketplace add /path/to/wstack --scope user
claude plugin install wstack@wstack --scope user

# 某一个项目（在该项目目录里执行）
claude plugin marketplace add /path/to/wstack --scope project
claude plugin install wstack@wstack --scope project
```

会话里等价于 `/plugin marketplace add` 然后 `/plugin install wstack@wstack`。

### Codex

个人（所有项目都能用）：

```bash
codex plugin marketplace add /path/to/wstack
codex plugin add wstack@wstack
```

只给某一个项目：在该仓库把本插件链到 `plugins/wstack`，并写入 `.agents/plugins/marketplace.json`，`source.path` 用 `./plugins/wstack`（相对该仓库根，不是本文件里的 `"."`）。然后在该仓库里执行 `codex plugin add wstack@wstack`。

### Cursor

推到 Git 之后，在 Customize 里把这个仓库加为 marketplace，安装 `wstack` 时选 **user** 或 **project**。

还没推远程、只在这台机器上用：把本仓库**复制**到 `~/.cursor/plugins/local/wstack`（Cursor 不加载指向仓库外的符号链接），然后 Reload Window。这是用户范围。项目范围走上面的 marketplace 安装。

### Grok

个人：

```bash
grok plugin install /path/to/wstack --trust
```

装完默认是关的。在 `~/.grok/config.toml` 里打开：

```toml
[plugins]
enabled = ["wstack"]
```

某一个项目：把本仓库放到该项目的 `.grok/plugins/wstack`（项目插件需要 trust）。

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
