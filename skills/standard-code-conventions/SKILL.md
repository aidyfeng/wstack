---
name: standard-code-conventions
description: >
  Python + TypeScript 全栈项目的命名与代码风格约定、结构化日志规范。新建类/文件/表/迁移、
  拿不准某个东西该叫什么、配置日志、给日志加字段时查这里。
  含一条排查坑：启动期自动迁移会重配 logging，把「服务已就绪」那行日志吞掉，所以**不能靠
  日志判断服务起没起来**，唯一可靠判据是健康检查端点返回。
  预设 structlog（或同类结构化日志）+ 领域实体与 ORM 模型分离的分层架构。
---

# 命名与代码风格约定

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

同一件东西在仓库里只有一个叫法——这是本篇的全部目的。命名不一致的代价不是难看，是 grep
不到：想找"所有 Repository 实现"时，`XxxRepo` / `XxxRepository` / `XxxStore` 三种写法会让
搜索漏掉三分之二。

---

## 命名表

### Python

| 类型 | 格式 | 例 |
|---|---|---|
| 领域实体 | PascalCase，`@dataclass` | `class UserSkill(BaseEntity)` |
| 值对象 | PascalCase | `class PhoneNumber` |
| 异常类 | `{Domain}Exception` | `class UserNotFoundException` |
| ORM 模型 | `{Entity}Model` | `class AdminUserModel(BaseModel)` |
| 请求/响应 Schema | `{Name}Request` / `{Name}Response` | `class OnboardingRequest` |
| Repository 接口 | `I{Entity}Repository`（`Protocol`） | `class IAudioAssetRepository(Protocol)` |
| Repository 实现 | `{ORM框架}{Entity}Repository` | `class SqlAlchemyAudioAssetRepository` |
| UseCase | `{Action}UseCase` | `class SaveOnboardingUseCase` |
| 私有成员 | `_` 前缀 | `_add_trace_id()` |
| 模块文件 | snake_case | `value_objects.py` |

接口用 `I` 前缀、实现用技术前缀（`SqlAlchemy` / `Redis` / `Aliyun`），一眼能看出"这是抽象还是
某个具体技术的实现"，也让同一接口的多实现自然并列。

### TypeScript

| 类型 | 格式 | 例 |
|---|---|---|
| 组件 | `PascalCase.tsx` | `WaveMark.tsx` |
| Hook | `use{Name}.ts` | `useCompanion.ts` |
| API service | `{feature}-api.ts` | `companion-api.ts` |
| 常量 | UPPER_SNAKE_CASE | `MOCK_GROUPS` |
| 类型/接口 | PascalCase | `interface ApiResponse<T>` |

### 数据库

| 类型 | 格式 | 例 |
|---|---|---|
| 表名 | snake_case **复数** | `emotion_logs` |
| 列名 | snake_case | `created_at` |
| 普通索引 | `idx_{table}_{columns}` | `idx_users_status_active` |
| 唯一索引 | `uq_{table}_{columns}` | `uq_identities_anonymous_id` |
| 迁移文件 | 时间戳前缀 `{timestamp}_{slug}.py` | `20260806_000001_plan_catalog.py` |

迁移文件是**迁移工具生成的 Python 脚本，不是 `.sql`**。命名格式由迁移工具的配置项决定，改格式
要去改配置，不是手工重命名。

---

## 代码风格

**严格类型**：Python 全量 type hint、TypeScript strict mode。**避免用 `dict` / `Any` 传参**——
它把契约从编译期推迟到运行时，而运行时出错的是用户不是你。

**单个函数不超过 200 行**——超了就是在一个函数里做了多件事，拆开。

**模块封装**：

- 每个包在 `__init__.py` 里显式导出对外接口，**不允许外部模块直接 import 包内实现细节**
- Python 私有成员 `_` 前缀
- 用某个内部包前先读它的 `__init__.py`；改完包的对外接口，同步更新那里的说明

**分层里的类型选择**（与分层架构配套）：领域实体用 `@dataclass`（不依赖 ORM 或校验框架），
API 请求/响应 Schema 与配置用 pydantic。让领域层不被框架污染是分层的意义所在。

**改完就删干净**：自己的改动造成的死代码（不再被引用的函数、import、常量）当次清掉。留着
"以后可能有用"的死代码，下一个人既不敢删也不敢改——他无法判断那是遗留还是有人在用。

---

## 结构化日志

**用结构化日志库，字段走关键字参数，不要拼字符串：**

```python
logger = get_logger(__name__)
logger.info("operation completed", user_id=user_id, result=result)   # ✅ 可检索、可聚合
logger.info(f"operation completed for {user_id}")                    # ❌ 只能全文搜
```

**处理器链顺序是固定的，新增 processor 插进链里而不是打乱它：**

```
merge_contextvars → add_logger_name → add_log_level → 注入 trace_id → 时间戳 → renderer
```

`trace_id` 从 contextvars 注入（配合请求中间件），**业务代码不用手动传**——这是链式处理器最大
的价值，任何一行日志都自动带上请求标识。

**renderer 按环境选，判据要写清楚**：只有生产用 JSON renderer，其余环境（含 staging /
集成测试 / e2e）都用控制台格式。注意这不是"只有 dev 用控制台"——写成 `if dev` 会让 staging
输出难读的 JSON。

**错误日志用 `logger.exception()`**，它自动带堆栈。

### 坑：不要靠日志判断服务起没起来

启动期若有自动迁移之类的步骤，**迁移工具会重新配置 logging**，把它之后本该打印的"服务已就绪"
那行吞掉——终端上日志停在迁移工具的最后一行，看起来像卡住了，实际服务早已就绪。

唯一可靠的判据是**健康检查端点返回成功**。用日志停更来判断"是不是挂了"会得出完全错误的结论，
而且会让人去查一个根本不存在的启动问题。

---
