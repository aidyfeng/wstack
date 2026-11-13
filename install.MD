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

安装后开启新会话。运行 `/plugin` 查看已安装插件，确认 `wstack` 已启用。

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

安装后开启新会话，在 `/plugins` 中确认 `wstack` 已安装并启用。如果使用桌面端，重启应用后检查插件列表。

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

如果通过手动复制安装了 `standard-*` 或 `wayne-mode`，需要单独删除对应副本；插件卸载命令不会处理这些文件。如果把插件克隆到项目目录并手动配置了 marketplace，则移除对应配置条目和插件目录，保留其他插件及技能。
