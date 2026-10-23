---
name: standard-dev-workflow
description: >
  提交：写 Conventional Commits、确认根因后修 bug、核对 pre-commit 的 files 覆盖，或给评审意见分级时使用。
---

# 开发协作流程

## 提交信息

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

| type | 用于 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修复缺陷 |
| `refactor` | 重构，不改变外部行为 |
| `perf` | 性能优化 |
| `test` | 增改测试 |
| `docs` | 文档 |
| `style` | 格式，不影响逻辑 |
| `build` | 构建系统 / 依赖 |
| `ci` | CI 配置 |
| `chore` | 杂项 |

`type` 小写，冒号后加一个空格。`scope` 可选，括号包住变更范围。`description` 用祈使语气、首字母小写、结尾不加句号。

body 与 description 空一行，写动机和上下文，不复述 diff。破坏性变更在 footer 写 `BREAKING CHANGE: <description>`，或在 type 后加 `!`。

```
feat(knowledge): add vector search for documents
fix: resolve token refresh race condition

refactor(auth)!: migrate session storage backend

BREAKING CHANGE: 旧的会话记录在升级后失效，用户需重新登录
```

## Bugfix

1. 理解现象，核实根因。能复现时先复现。
2. 评估方案、副作用和本次授权范围。关键事实缺失时先询问。
3. 在已授权范围内改。项目明确要求额外批准时遵守该约定。
4. 按改动范围验证，并报告结果。

验证范围、执行时机和行为证据按 [quality playbook](../wayne-mode/playbooks/quality.md)。已有测试契约随行为变化更新；测试原则及 pstack 可用性按 [standard-quality-gates](../standard-quality-gates/SKILL.md)。

## 提交前门禁

本地 pre-commit 通常包含：

| 类别 | 工具 |
|---|---|
| Python | lint（带 `--fix`）、format、静态类型检查 |
| TypeScript | ESLint（带 `--fix`）、`tsc --noEmit`、Prettier |
| 通用 | 行尾空白、文件末尾换行、YAML 语法、大文件拦截 |

```bash
pre-commit run --all-files      # 手动全量
git commit -m "..."             # 自动触发
```

让代码通过现有钩子。改钩子配置把检查放行，放行的往往是该留的那条规则。

两个缺口都不会提示：

`files` 正则常常只写了最初那个目录。后来加的前端或子包一个钩子都不触发。

钩子通常只跑 lint、format、类型检查，不跑测试。

提交前看配置里的 `files` 覆盖了哪些路径。覆盖外的改动手动跑对应的 lint、format 和类型检查。pre-commit 全绿只证明执行过的静态检查通过；行为与构建验证按 quality playbook。

## 代码评审

**设计与架构** —— 是否符合整体架构，职责是否单一，有没有不必要的依赖或循环依赖，有没有可复用的现有代码，有没有过度设计。

涉及 DDD 后端时按 `standard-fastapi-ddd-backend` 逐项核对，建表与迁移时按 `standard-sqlalchemy-persistence` 逐项核对。业务功能测试通过不代替这两份技能里的检查。

**代码质量** —— 命名是否准确，函数是否过长，有没有 copy-paste，异常处理和错误信息是否有意义，空值和边界输入有没有处理。

**安全性** —— 输入是否验证和清理，查询是否参数化，输出是否转义，有没有硬编码密钥，日志是否泄露敏感数据，访问控制是否到位。细则见 `standard-api-security-baseline`。

**性能** —— 复杂度是否合理，有没有 N+1，索引用得对不对，连接和文件句柄是否释放，缓存失效是否正确，并发下有没有竞态。

**文档与注释** —— 复杂逻辑有没有解释原因。注释写为什么。PR 描述写清变更内容和原因。

### 反馈分级

| 级别 | 含义 | 处理 |
|---|---|---|
| `[Blocker]` | 必须修复才能合入 | 必须改 |
| `[Major]` | 强烈建议修复 | 应该改，除非有充分理由 |
| `[Minor]` | 可改进 | 可选 |
| `[Question]` | 需要作者解释 | 需回复 |
| `[Nit]` | 写得好的地方 | 无需处理 |

每条意见标级别。不标级别时，作者会把意见当成同等重量。

## 自查

1. `pre-commit run --all-files`，修完报出的问题。
2. 按上面的清单过一遍变更。
3. 给出问题与改进建议。
4. 修完再扫，直到没有问题。
5. 按 quality playbook 完成所需验证，报告实际证据与未验证项。
6. 按提交信息规范提交。
