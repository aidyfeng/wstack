# 安装与卸载

先安装 [P Stack](#前置依赖p-stack)，再按客户端选择安装方式：

| Agent / 客户端 | 安装方式 |
| --- | --- |
| [Claude Code](#claude-code) | GitHub marketplace，支持个人或项目范围 |
| [Codex](#codex) | GitHub marketplace；项目范围也可使用 Skills CLI |
| [Cursor](#cursor) | 从 GitHub 克隆到个人插件目录；项目范围可使用 Skills CLI |
| [Grok Build](#grok-build) | 直接从 GitHub 安装插件 |
| [其他 Agent](#其他-agentskills-cli) | 使用 Skills CLI 选择客户端并安装技能 |

下文终端命令使用 Bash；以 `/` 开头的命令在对应客户端的会话输入框执行。插件安装与 Skills CLI 安装选择一种即可，避免同一技能重复加载。

## 前置依赖：P Stack

wstack 基于 poteto（Lauren Tan）的 P Stack 封装领域规范，不包含或自动安装 P Stack。完整工作流要求两者安装在同一个客户端中。

**Cursor**：在会话中执行：

```text
/add-plugin pstack
```

安装后运行 `/setup-pstack`。

**Claude Code**：在会话中分两次发送：

```text
/plugin marketplace add cursor/plugins
```

```text
/plugin install pstack@cursor-plugins
```

安装后运行 `/pstack:setup-pstack`。

**其他客户端**：先按 [P Stack 上游说明](https://github.com/cursor/plugins/blob/main/pstack/README.md#install) 确认是否有对应适配，并完成安装。仅复制技能不代表已适配上游依赖的工具、模型分工和客户端能力。

开启新会话，确认能发现 `poteto-mode` 和任务所需的 P Stack 技能，再使用 wstack。缺少适配时可以独立使用 standard skill，但完整工作流的前置依赖尚未满足。

## wayne-mode 自动启用与开关

### 支持范围与前提

本次协议核对日期为 2026-11-13。Claude Code 和 Codex 插件通过 `SessionStart` 注入 `skills/wayne-mode/SKILL.md` 的实际正文及技能目录，通过 `UserPromptSubmit` 识别控制消息、更新状态并追加上下文。不会复制规则到第二份文件，也不会只提示模型自行加载技能。Playbook 和 standard skill 仍按正文中的路由按需读取。

| 客户端 / 安装方式 | 本仓库的自动开关支持 |
| --- | --- |
| Claude Code 插件 | 支持；恢复及压缩后的 `SessionStart` 按会话状态重新注入 |
| Codex 插件 | 支持；须允许 hooks 并审查、信任插件 hook；恢复及压缩后保持会话状态 |
| Cursor 插件 | 保留按需技能；不注册自动开关 |
| Grok Build 插件 | 保留按需技能；这两个事件不支持所需的上下文注入 |
| 仅 Skills CLI 或手动复制技能 | 只安装技能，不注册 hook，不提供自动开关 |

运行时使用已有 Python 3 标准库，无第三方包。Linux、macOS 及 Claude Code 的 Windows 环境需要 `python3` 能从客户端非交互环境的 `PATH` 调用；Codex 的 Windows hook 使用 Python 3 启动器 `py -3`。先在客户端实际使用的终端确认运行时可用。缺少运行时、未信任 hook、客户端禁用 hooks 或版本不支持这些事件时，自动开关不会运行，技能仍可按需加载。

Cursor 的原生事件为 `sessionStart`、`beforeSubmitPrompt`、`preCompact`，不能直接使用 Claude/Codex 的大写事件配置。官方 `beforeSubmitPrompt` 输出只列出 `continue`、`user_message`，没有本功能所需的上下文追加协议；ponytail 的 Cursor 适配依赖客户端未公开的 `additional_context` 行为，且云端不触发 `sessionStart`。本仓库不据此宣称可靠的会话切换与压缩恢复，也不安装静态常驻规则来假装可以关闭。

Grok Build 的官方文档及源码在提交 `2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8` 中明确：`SessionStart` 为观察型事件，stdout 被忽略；`UserPromptSubmit` 放行时丢弃 stdout 和 `additionalContext`。压缩使用 `PreCompact`、`PostCompact` 观察事件，无法满足本功能的上下文恢复要求。虽然支持 hook 文件和 Claude 兼容环境变量，本仓库仍不注册开关，避免只更新磁盘状态却让模型继续执行旧规则。

### 会话命令

命令作为单独一行的会话消息发送，不是终端命令：

| 消息 | 效果 |
| --- | --- |
| `/wayne-mode on` | 仅开启当前会话，并注入实际规则 |
| `/wayne-mode off` | 仅关闭当前会话，追加停用此前自动注入规则的指令 |
| `/wayne-mode status` | 报告当前会话状态及后续新会话默认值 |
| `/wayne-mode default on` | 持久化新会话默认开启，当前及已初始化的其他会话不变 |
| `/wayne-mode default off` | 持久化新会话默认关闭，当前及已初始化的其他会话不变 |

初始默认值为 `on`。Claude Code 插件技能带命名空间，请使用 `/wstack:wayne-mode on`、`/wstack:wayne-mode off`、`/wstack:wayne-mode status`、`/wstack:wayne-mode default on` 和 `/wstack:wayne-mode default off`。hook 同时识别不带命名空间的原始消息，但插件没有注册全局的同名内建命令。

Codex CLI 会在发送前拒绝未知的 `/wayne-mode` 斜杠命令。请在输入框中先键入一个空格，再输入命令，按普通消息发送，例如下面每行 `/` 前都有一个空格：

```text
 /wayne-mode status
 /wayne-mode off
 /wayne-mode on
 /wayne-mode default off
 /wayne-mode default on
```

hook 只接受整条控制消息；支持首尾水平空白，不从代码块、多行粘贴、解释文字或附带任务中执行开关。无效参数不会修改开关。收到命令后的简短确认来自追加的上下文；如果客户端没有运行 hook，不能把模型口头承诺视为状态已经保存。

恢复同一会话及上下文压缩时复用原会话状态；新建或清空后使用新会话标识的会话才读取新默认值。关闭会追加明确的停用指令，后续消息继续携带关闭标记，防止摘要或同名技能内容重新激活自动规则。已发送的历史 token 无法撤回，模型是否遵循停用指令仍取决于客户端和模型。用户、项目和独立安装的 P Stack 规范不受此开关控制。

### 状态、失败保护与清理

状态保存在用户目录，所有支持的客户端共享新会话默认值，各客户端与会话分别保存当前状态：

| 系统 | 基础目录 |
| --- | --- |
| Linux / 其他 Unix | `$XDG_CONFIG_HOME/wstack/wayne-mode`，未设置时为 `~/.config/wstack/wayne-mode` |
| macOS | `~/Library/Application Support/wstack/wayne-mode` |
| Windows | `%APPDATA%\wstack\wayne-mode`，未设置时回退到用户目录下的 `AppData\Roaming\wstack\wayne-mode` |

`config.json` 只保存默认开关；`sessions/` 中的会话快照只保存当前开关，文件名由客户端标识和会话 ID 的 SHA-256 摘要组成。不记录提示词、项目路径、会话原文、token 或密钥。写入采用原子替换。保留会话快照是为了跨进程恢复原会话，因此不会在会话退出时删除。

每次 hook 最多运行 5 秒。脚本遇到非法输入、缺少会话 ID、损坏配置、读写失败或规则文件缺失时，输出简短警告并正常退出，不阻断用户消息或会话，也不声称开关已经成功。配置或状态损坏不会被静默重置为开启。启动器本身不可用或超时时，由客户端继续处理；必要时检查客户端 hooks 面板或日志，修复后重试命令。

卸载插件后 hook 随插件移除，用户目录中的状态保留。关闭仍在使用的客户端后，可删除上述基础目录中的 `sessions/` 清理所有会话快照，删除 `config.json` 恢复默认开启，或删除整个 `wayne-mode/` 目录清理本功能全部状态。清理快照后恢复旧会话也会重新读取默认值；保留其他 wstack 文件及其他插件配置。

协议参考：[ponytail hooks 与安装机制](https://github.com/DietrichGebert/ponytail/blob/main/INSTALL.md)、[Claude Code hooks](https://code.claude.com/docs/en/hooks)、[Claude Code 技能命名空间](https://code.claude.com/docs/en/skills)、[Codex hooks](https://learn.chatgpt.com/docs/hooks)、[Codex 插件打包](https://developers.openai.com/plugins/build/plugins)、[Codex 输入框源码](https://github.com/openai/codex/blob/main/codex-rs/tui/src/bottom_pane/chat_composer.rs)、[Cursor hooks](https://cursor.com/docs/hooks)、[ponytail Cursor 协议核对](https://github.com/DietrichGebert/ponytail/blob/main/docs/cursor-hooks.md)、[Grok Build hooks](https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-pager/docs/user-guide/10-hooks.md)、[Grok 输出丢弃测试](https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-hooks/src/dispatcher.rs#L1631)。

## Claude Code

### 安装

在会话中分两次发送：

```text
/plugin marketplace add aidyfeng/wstack
```

```text
/plugin install wstack@wstack
```

`aidyfeng/wstack` 是 GitHub 仓库的 `owner/repo` 简写，无需填写本地路径。添加 marketplace 注册插件来源，安装命令再从中安装插件；`wstack@wstack` 分别表示插件名和 marketplace 名。

也可以在终端明确指定范围。个人安装对所有项目生效：

```bash
claude plugin marketplace add aidyfeng/wstack --scope user
claude plugin install wstack@wstack --scope user
```

只安装到一个项目时，在该项目根目录执行：

```bash
claude plugin marketplace add aidyfeng/wstack --scope project
claude plugin install wstack@wstack --scope project
```

安装后开启新会话。运行 `/plugin` 查看已安装插件，确认 `wstack` 已启用；按[开关说明](#wayne-mode-自动启用与开关)确认 Python 3 可用，再发送 `/wstack:wayne-mode status` 检查会话开关。

### 卸载

卸载个人安装：

```bash
claude plugin uninstall wstack@wstack --scope user
```

卸载项目安装时，在对应项目根目录执行：

```bash
claude plugin uninstall wstack@wstack --scope project
```

如果还要移除插件来源，按原安装范围执行其中一条：

```bash
claude plugin marketplace remove wstack --scope user
claude plugin marketplace remove wstack --scope project
```

个人和项目范围都装过时，需要分别卸载。项目范围的卸载会改变共享项目配置。

参考：[Claude Code 插件管理](https://code.claude.com/docs/en/plugins/install)。

## Codex

### 安装

在终端执行：

```bash
codex plugin marketplace add aidyfeng/wstack
codex plugin add wstack@wstack
```

安装后在 `/plugins` 中确认 `wstack` 已安装并启用，打开 `/hooks` 审查并信任它的 `SessionStart`、`UserPromptSubmit` hook，再开启新会话。如果使用桌面端，重启应用后检查插件列表。hooks 被客户端或管理员关闭时自动开关无效；按[开关说明](#wayne-mode-自动启用与开关)发送带前导空格的状态消息检查。

只希望当前项目使用技能时，可选择下方 [Skills CLI](#其他-agentskills-cli)，使用 `--agent codex` 且不加 `--global`。

### 卸载

先卸载插件：

```bash
codex plugin remove wstack@wstack
```

如果还要移除插件来源，再执行：

```bash
codex plugin marketplace remove wstack
```

也可以在 `/plugins` 中选择 `wstack` 并卸载。通过 Skills CLI 安装的技能，按 [Skills CLI 卸载步骤](#卸载-skills-cli-安装的技能)处理。

参考：[OpenAI 插件管理](https://learn.chatgpt.com/docs/plugins)、[GitHub marketplace 配置](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli)。

## Cursor

### 安装

本仓库提供 Cursor 插件配置。对于直接从 GitHub 获取、尚未通过官方 Marketplace 安装的插件，可以克隆到 Cursor 的个人插件目录：

```bash
git clone https://github.com/aidyfeng/wstack.git ~/.cursor/plugins/local/wstack
```

重启 Cursor，或在命令面板执行 `Developer: Reload Window`。打开 Customize，确认个人范围下的 `wstack` 及其技能可见。该方法要求允许导入本地插件；不要把目录替换为指向其他位置的符号链接。

此安装只提供按需技能加载，不注册 wayne-mode 自动开关；`/wayne-mode on/off/default/status` 不会通过本插件更新任何状态，详见[支持范围](#支持范围与前提)。

只安装到当前项目时，可选择下方 [Skills CLI](#其他-agentskills-cli)，使用 `--agent cursor` 且不加 `--global`。

### 卸载

通过上述克隆方式安装的插件，删除 `~/.cursor/plugins/local/wstack` 目录，再执行 `Developer: Reload Window`。如果在该目录改过文件，删除前先保存修改。

如果此前通过 Marketplace 安装，在 Customize 中找到对应范围的 `wstack`，选择卸载。通过 Skills CLI 安装的技能，按 [Skills CLI 卸载步骤](#卸载-skills-cli-安装的技能)处理。

参考：[Cursor 插件与本地加载说明](https://cursor.com/docs/plugins)。

## Grok Build

### 安装

在终端执行：

```bash
grok plugin install aidyfeng/wstack --trust
grok plugin enable wstack
```

`--trust` 表示信任该插件来源。安装后开启新会话，使用以下命令检查安装情况：

```bash
grok plugin list
```

此安装提供按需技能，不注册 wayne-mode 自动开关。Grok Build 的 `SessionStart` 和放行的 `UserPromptSubmit` 输出不会成为模型上下文，因此 `/wayne-mode on/off/default/status` 不会通过本插件更新状态；详见[支持范围](#支持范围与前提)。

### 卸载

```bash
grok plugin uninstall wstack
```

直接从 GitHub 安装不需要额外注册 marketplace。如果此前单独添加过该来源，还可以执行 `grok plugin marketplace remove wstack`；该操作会连同来源中的插件一起移除。

参考：[Grok Build 插件管理](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/09-plugins.md)。

## 其他 Agent：Skills CLI

GitHub Copilot、Gemini CLI、OpenCode、Amp、Kimi Code CLI、Pi、Windsurf 等客户端，可以通过 [Skills CLI](https://github.com/vercel-labs/skills) 安装本仓库的技能。此方式安装 `skills/` 内容，不注册 wstack 插件，也不自动安装 P Stack。

需要 Git，以及符合 [Skills CLI 当前要求](https://github.com/vercel-labs/skills#install-a-skill) 的 Node.js / npm；当前最低 Node.js 版本为 22.20。

### 安装

在目标项目根目录执行，按提示选择本仓库全部技能、目标 Agent 和安装方式：

```bash
npx skills add aidyfeng/wstack
```

默认只对当前项目生效。个人安装使用：

```bash
npx skills add aidyfeng/wstack --global
```

也可以指定 Agent。下表中的参数可直接附在安装命令后；`--skill '*'` 表示安装本仓库全部技能：

| Agent | 参数 |
| --- | --- |
| Claude Code | `--agent claude-code` |
| Codex | `--agent codex` |
| Cursor | `--agent cursor` |
| Grok Build | `--agent grok` |
| GitHub Copilot | `--agent github-copilot` |
| Gemini CLI | `--agent gemini-cli` |
| OpenCode | `--agent opencode` |
| Amp | `--agent amp` |
| Kimi Code CLI | `--agent kimi-code-cli` |
| Pi | `--agent pi` |
| Windsurf | `--agent windsurf` |

例如，只给当前项目的 Codex 安装全部技能：

```bash
npx skills add aidyfeng/wstack --skill '*' --agent codex
```

完整客户端列表见 [Skills CLI 支持的 Agent](https://github.com/vercel-labs/skills/blob/main/docs/agents.md)。安装后开启新会话，确认 `wayne-mode`、`standard-quality-gates` 等技能可见。

### 卸载 Skills CLI 安装的技能

按仓库来源卸载，避免逐个列举技能名。在原项目根目录执行：

```bash
npx skills remove aidyfeng/wstack
```

个人安装使用：

```bash
npx skills remove aidyfeng/wstack --global
```

只卸载某个 Agent 的安装时，追加与安装时相同的 `--agent` 参数，例如：

```bash
npx skills remove aidyfeng/wstack --agent codex
```

按提示确认要移除的技能和客户端。参考：[Skills CLI 安装与卸载命令](https://github.com/vercel-labs/skills/blob/main/docs/commands.md)。

## 卸载后检查

卸载后开启新会话，确认插件或技能列表中不再出现本次安装的 wstack 内容。P Stack 是独立安装的前置依赖，卸载 wstack 不需要同时卸载 P Stack。

如果通过手动复制安装了 `standard-*` 或 `wayne-mode`，需要单独删除对应副本；插件卸载命令不会处理这些文件。如果把插件克隆到项目目录并手动配置了 marketplace，则移除对应配置条目和插件目录，保留其他插件及技能。自动开关的用户状态按[状态清理说明](#状态失败保护与清理)另行删除；已经打开的会话仍可能保留历史注入内容，需结束旧会话后再检查。
