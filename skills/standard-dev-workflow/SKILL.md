---
name: standard-dev-workflow
description: >
  开发协作流程规范——提交信息格式（Conventional Commits）、Bugfix 的先确认后修复流程、
  本地 pre-commit 质量门禁、代码评审清单与反馈分级。写 commit message、修 bug、提交前自查、
  评审别人或自己的改动时使用。
  一条要认清的：**pre-commit 通过不等于测试通过**——这类门禁通常只跑 lint/format/type-check，
  不跑测试；且它的 files 正则常常只覆盖仓库的一部分目录，另一半改动根本不触发检查。
  提交前先确认门禁到底覆盖了哪些路径，别把"钩子绿了"当成质量保证。
---

# 开发协作流程

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

---

## 提交信息：Conventional Commits

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

- `type` 小写，后跟冒号加空格；`scope` 可选，括号包裹，写变更范围
- `description` 用祈使语气、首字母小写、结尾不加句号
- `body` 与 description 空一行，写**动机与上下文**——"改了什么"看 diff 就知道，commit message
  该回答的是"为什么"
- 破坏性变更：footer 写 `BREAKING CHANGE: <description>`，或在 type 后加 `!`

```
feat(knowledge): add vector search for documents
fix: resolve token refresh race condition

refactor(auth)!: migrate session storage backend

BREAKING CHANGE: 旧的会话记录在升级后失效，用户需重新登录
```

---

## Bugfix：确认问题后修复

1. 理解现象，核实根因；能复现时先复现。
2. 评估方案、副作用与本次授权范围；关键事实缺失时先询问。
3. 在已授权范围内实施；项目明确要求额外批准时遵守该约定。
4. 按改动范围验证并报告结果，具体命令从当前项目地图读取。

验证范围、执行时机和行为证据按 [quality playbook](../wayne-mode/playbooks/quality.md)。已有测试契约随行为变化更新；测试原则及 pstack 可用性按 [standard-quality-gates](../standard-quality-gates/SKILL.md)。

---

## 提交前门禁

本地 pre-commit 钩子通常包含：

| 类别 | 工具 |
|---|---|
| Python | lint（带 `--fix`）、format、静态类型检查 |
| TypeScript | ESLint（带 `--fix`）、`tsc --noEmit`、Prettier |
| 通用 | 行尾空白、文件末尾换行、YAML 语法、大文件拦截 |

```bash
pre-commit run --all-files      # 手动全量
git commit -m "..."             # 自动触发
```

**不要改配置文件来绕过检查**——绕过的那条规则通常正是最该遵守的那条。

### ★ 门禁覆盖范围要自己确认

两个普遍存在的缺口，**它们不会以任何形式提示你**：

**① `files` 正则常常只覆盖部分目录。** 多前端/多包仓库里，钩子的 `files` 往往只写了当初那一个
目录的路径前缀，后来新增的前端或子包**一个钩子都不触发**——规则写得再严也不拦。

**② 这类门禁通常不跑测试**，只有 lint / format / type-check。后端逻辑改了、测试有没有过，
钩子完全不知道。

所以：**pre-commit 全绿 ≠ 代码没问题**。提交前先看一眼配置里的 `files` 正则覆盖了哪些路径，
不在覆盖范围内的改动手动跑对应的静态检查；行为与构建验证按 quality playbook。

---

## 代码评审

### 检查清单

**设计与架构** —— 是否符合整体架构？职责是否单一？有无不必要的依赖或循环依赖？有没有可复用
的现有代码？是否过度设计？

涉及 DDD 后端或建表时，按 `standard-fastapi-ddd-backend` 与
`standard-sqlalchemy-persistence` 逐项核对：用例位于 `application/use_cases/`；
有身份的领域实体继承公共 `BaseEntity`；业务 ORM 继承公共 `BaseModel` 且公共列已落库；
模型与迁移升级后的数据库均无物理外键。仅共享 metadata 不算继承，业务功能测试通过不代替这些检查。
项目绑定中的“待确认”不构成例外授权；有冲突应核实用户指令，不能把实现后的偏离补记为默认规则。

**代码质量** —— 命名是否准确？函数是否过长？有无 copy-paste？异常处理是否完善、错误信息是否
有意义？空值与边界输入处理了吗？

**安全性** —— 输入是否验证清理？是否参数化查询？输出是否转义？有无硬编码密钥？日志是否泄露
敏感数据？访问控制是否到位？（细则见 `standard-api-security-baseline`）

**性能** —— 复杂度是否合理？有无 N+1 查询？索引用对了吗？连接/文件句柄是否释放？缓存失效
策略是否正确？并发下有无竞态？

**文档与注释** —— 复杂逻辑有没有解释？注释是否说明**为什么**而非"怎么做"？PR 描述是否讲清了
变更内容与原因？

### 反馈分级

标记出级别，让作者知道哪些必须改、哪些可以商量：

| 级别 | 含义 | 处理 |
|---|---|---|
| `[Blocker]` | 必须修复才能合入 | 必须改 |
| `[Major]` | 强烈建议修复 | 应该改，除非有充分理由 |
| `[Minor]` | 可改进 | 可选 |
| `[Question]` | 需要作者解释 | 需回复 |
| `[Nit]` | 写得好的地方 | 无需处理 |

不分级的评审会让作者把所有意见当同等重量，要么全改（浪费时间）要么全不改（漏掉真问题）。

### 自查顺序

1. `pre-commit run --all-files`，修完所有报出的问题
2. 按上面的清单逐项过一遍变更
3. 给出问题与改进建议
4. 修完重新扫，直到无问题
5. 按 quality playbook 完成所需验证，报告实际证据与未验证项
6. 按提交信息规范提交

---

## 授权与项目协作约定

按当前用户的明确授权和项目地图中的协作约定执行。架构、依赖、质量门、提交及发布是否
需要额外批准，由当前项目声明；已有明确授权时不重复确认。不把某个项目的审批要求套到所有项目。

---
