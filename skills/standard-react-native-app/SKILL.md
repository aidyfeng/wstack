---
name: standard-react-native-app
description: >
  React Native + Expo 应用规范——与小程序端的同构约定、原生能力封装边界、
  版本号与上架号段、签名策略、monorepo 下的 Metro 配置、iPad 支持的前置条件。
  写用户应用页面（含 Expo Web 网页版）、接原生能力、配构建与发版时使用。
  网页版、安卓、iOS 是同一个 Expo 工程。网页在浏览器里开（pnpm web），不写进 Next.js。
  本仓库装了 expo-dev-client，手机用 Development Build；商店里的 Expo Go 打不开它。
  两条会浪费整轮构建的硬约束：iOS 的 marketing version 一旦上架就永久关闭，
  再传任何 build 都会在**最后一步**被拒（前面构建资源已全部消耗）；
  Expo 的 React / RN 版本组合必须用官方矩阵，手写 latest 会装出不被支持的组合。
  一条默认就开着、不做就出丑的：ios.supportsTablet 默认为真，UI 没适配时
  iPad 上是全屏拉伸，比不支持更难看，而声明支持后审核员会真的用 iPad 测。
  预设 Expo（含 EAS）+ pnpm workspace 共享包；不覆盖裸 RN 工程。
---

# React Native + Expo

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

## ★ 与小程序端的 features 保持同构

两端 `features/` **同名、同结构**：一样的 feature 名，一样的 `hooks/` / `services/` /
`components/` 划分。

配套硬约束：**`hooks/` 与 `services/` 必须宿主无关**——不许 import `react-native`，
需要原生能力时一律经 `platform/`。

守住这条，两端差异只剩组件层，业务逻辑整层可平移。

---

## ★ 版本矩阵不要手写

Expo 每个 SDK 版本对应特定的 React 与 React Native 版本。**用官方 CLI 初始化，
或用 `expo install` 装依赖**，让它决定版本。

手写"最新版"会装出 Expo 不支持的组合——比如 SDK 57 对应的是 RN 0.86.x，
而 npm 上的最新是 0.87.x。这类不匹配的表现往往是运行时的诡异错误，不是安装期报错。

升级 SDK 走 `expo install --fix`，不要逐个包手动改版本号。

---

## 目标平台与 Web 边界

由项目地图声明 Expo 的目标平台和用户应用归属。项目采用 iOS／Android／Web 三端时，
保留其 platforms 与 Web 配置，Web 与原生差异用平台文件或平台层实现；仅原生项目不强制启用 Web。
业务 hook/service 保持宿主无关，DOM 组件不得导入原生界面。采用哪种路由器按项目现状确认。

## 三端与手机上的客户端

`app.json` 的 `platforms` 同时有 `ios`、`android`、`web`。同一份 `src/app` 跑三端。
`pnpm start` 起开发服务器；`pnpm web` 在浏览器打开网页版；安卓和 iOS 连同一台服务器。

网页版跑在浏览器里（`react-native-web`），不跑在手机上的 Expo Go 里。

本仓库依赖了 `expo-dev-client`。这种工程不能用应用商店里的 Expo Go 扫码打开，手机要装自己的 Development Build（`expo run:android` / `expo run:ios`，或 EAS 的 development profile）。只改 JS 时 Metro 热更新，不必重装；原生依赖变了才要重建这个客户端。

没装 `expo-dev-client` 的项目才用 Expo Go。商店版 Expo Go 会落后于新 SDK，扫码可能报 `Project is incompatible with this version of Expo Go`。不要为此把 SDK 钉死在旧版。装新版 Expo Go；确实没有再降 SDK，并且走 `npx expo install --fix`，不要手写 expo / react / react-native 的版本组合。

---

## 原生能力必须经平台抽象层

`features/*` 里禁止直接 import 原生模块。所有原生能力包一层，放 `platform/`。

封装的三条：

1. **可用性探测**：模块不存在 / 当前平台不支持时，`isAvailable()` 返回 false，
   不抛错、不崩
2. **降级明确**：在文件头注释写清楚不可用时的行为——是静默 no-op、返回兜底值、
   还是上抛给调用方
3. **能拆成纯函数的拆出去**，并标注"纯模块，不依赖原生桥"——换来的是可以直接跑单测

### 降级方向要分清

**用户主动触发的操作失败要上抛**（登录、购买、分享）——用户点了按钮，什么都不发生
比报错更糟。

**后台/装饰性操作失败可以静默**（埋点、预取、媒体元数据上报），但要在注释里写明
`fire-and-forget`，与"掩盖故障"区分开。

### 密钥缺失时的取舍

第三方 SDK 的 appid / 密钥没注入时，让对应入口**静默不可用**（按钮不展示），
而不是展示一个必然失败的死按钮。

代价要知道：**配置遗漏本身也不会报警**。来源项目就踩过——CI 漏注入微信 appid，
登录页的微信入口整个消失，排查了很久才发现不是代码问题。接同类能力时权衡这两种坏
（死按钮 vs 静默消失），并在注释里写下选了哪个、为什么。

---

## ★★ iOS：marketing version 与 build number 是两套号段

- **marketing version**（商店显示的版本号）：只支持三段 `MAJOR.MINOR.PATCH`。
  版本号来源是四段的话必须截取前三段——Apple 完全不识别第四段
- **build number**：同一 marketing version 下必须递增且不重复。正确做法是查商店当前
  该 marketing version 下的最大 build number 再 +1，不要套用其他平台的版本编码公式
  （那类公式在 marketing version 不变时会持续算出相同数字，撞号被拒）

**硬约束：marketing version 一旦上架，这个号永久关闭**，再传任何新 build 都会被拒——
build number 递增救不了，商店卡的是 marketing version 这个字段本身。

真实代价：构建流程全程正常，卡在**最后一步上传**被拒，前面所有构建资源已经消耗完。
发布前先确认目标版本号没上架过。

---

## Android 签名：本地优先，CI 兜底，未签名不阻断

```
优先级：本地 keystore 文件 > 环境变量 > 未签名兜底（仅警告，不阻断）
```

- 不要把签名凭据硬编码进配置，也不要把 keystore 提交进版本控制
- 两者都缺失时构建**不应失败**，退化为未签名包 + 警告——否则没配凭据的开发环境
  连日常构建都跑不了
- 第三方 SDK 要求签名指纹一致时（微信登录等），可让 debug 变体在检测到本地凭据时
  复用 release 签名；CI 与其他开发者不受影响

EAS Build 走托管凭据时，这套优先级由 EAS 管理，但**本地 prebuild 构建仍适用**。

---

## ★ iPad 支持：默认开着，不做适配比不支持更难看

`ios.supportsTablet` 在 Expo 模板里**默认为 true**——这属于"不做决定也已经做了决定"。

开着但 UI 没适配的结果是全屏拉伸（1024pt 宽的按钮、单列长文本），比关掉后的
"居中黑边兼容模式"更难看。而且**声明支持 iPad 后，审核员会真的用 iPad 测**，
布局崩了按 2.1 / 4.0 打回。

真要支持，四件事缺一不可：

1. `orientation` 不能锁 `portrait`——iPad 的 Split View / Slide Over **要求支持所有方向**
2. 响应式：RN 没有 CSS media query，用 `useWindowDimensions()` 按断点分叉布局
3. 导航结构：手机底部 tab 在 iPad 上通常要改侧边栏或 split view
4. 图标与启动图出 iPad 尺寸

架构上不需要提前准备：共享包里的业务逻辑 iPad 完全复用，要分叉的只有组件层。

先想清楚值不值得：iPad 上 Safari 体验不差，若网页版已做响应式，原生 iPad 只在需要
离线、推送、或商店内购通道时才值得单独投入。

---

## monorepo 集成

先按项目地图与 workspace 配置确定工作区根，不把仓库根或 `ui/` 写成所有项目的固定路径。
Expo 的 monorepo 自动配置可用时沿用默认；有显式 Metro 配置时，核实共享源码与依赖真实路径
都在监听、解析范围内，并通过目标平台导出验证。修改目录布局后同步检查依赖链接。

## 发版与更新机制

Expo 有两套更新通道，**不要混为一谈**：

- **EAS Update**（OTA）：只能改 JS/资源，不能改原生代码。适合修文案、改逻辑
- **商店发版**：原生依赖变化、SDK 升级、权限变更必须走这条

判据：改动是否触及原生层。装了新的原生模块、改了权限声明、升了 SDK —— 一律商店发版。
OTA 推一个与原生层不匹配的 JS 包，表现是启动崩溃。

（不要自建"比对 CDN 上的 manifest 判断有无新版"那一套——那是没有 OTA 能力的方案的
变通做法，Expo 有 EAS Update 就不需要。）

---
