---
name: standard-code-conventions
description: >
  命名：新建 Python 或 TypeScript 的类、文件、表、迁移时使用。日志：配置 structlog
  字段，或凭健康检查判断服务是否就绪时使用。
---

# 命名与代码风格

同一概念只用下面一个名字。`XxxRepo`、`XxxRepository`、`XxxStore` 混用时，搜索会漏掉实现。

## 命名

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

接口用 `I` 前缀，实现用技术前缀（`SqlAlchemy` / `Redis` / `Aliyun`）。

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
| 表名 | snake_case 复数 | `emotion_logs` |
| 列名 | snake_case | `created_at` |
| 普通索引 | `idx_{table}_{columns}` | `idx_users_status_active` |
| 唯一索引 | `uq_{table}_{columns}` | `uq_identities_anonymous_id` |
| 迁移文件 | `{timestamp}_{slug}.py` | `20260806_000001_plan_catalog.py` |

迁移文件是迁移工具生成的 Python 脚本，不是 `.sql`。格式由迁移工具的配置决定，改格式改配置，不手工重命名文件。

## 代码风格

Python 写全量 type hint，TypeScript 用 strict mode。参数用具体类型。`dict` / `Any` 传参会把契约推迟到运行时。

单个函数不超过 200 行，超过就拆开。

每个包在 `__init__.py` 里显式导出对外接口。外部模块不直接 import 包内实现细节。用某个内部包之前先读它的 `__init__.py`；改了对外接口就同步改那里的说明。私有成员用 `_` 前缀。

领域实体用 `@dataclass`。请求/响应 schema 和配置用 pydantic。

当次删掉这次改动留下的、不再被引用的函数、import、常量。

## 结构化日志

字段走关键字参数：

```python
logger = get_logger(__name__)
logger.info("operation completed", user_id=user_id, result=result)   # 可检索、可聚合
logger.info(f"operation completed for {user_id}")                    # 只能全文搜
```

处理器链的顺序固定。新 processor 插进这条链，不重排已有顺序：

```
merge_contextvars → add_logger_name → add_log_level → 注入 trace_id → 时间戳 → renderer
```

`trace_id` 从 contextvars 注入（请求中间件写入）。业务代码不手传 `trace_id`。

只有生产用 JSON renderer。staging、集成测试、e2e 用控制台格式。写成 `if dev` 会让 staging 打出 JSON。

错误用 `logger.exception()`，它带堆栈。

启动期的自动迁移会重新配置 logging，把它后面的「服务已就绪」吞掉。终端停在迁移工具的最后一行时，服务可能已经就绪。判据是健康检查端点返回成功。
