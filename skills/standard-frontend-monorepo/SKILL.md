---
name: standard-frontend-monorepo
description: >
  前端 monorepo 规范——四个交付物（Next.js 站点 / Vite 后台 / Taro 小程序 / Expo App）
  与共享包的边界。建新 app、抽共享包、加跨端依赖、配 workspace、改构建配置时使用。
  按项目实际交付物裁剪，不预设官网、用户 Web 与原生端必须如何分工。
  几条容易踩的：小程序没有标准 fetch、连 Response 构造函数都没有；Taro 锁 React 18
  而 Next 16 与 Expo 57 要 React 19，共享包必须双版本兼容且不得用 19 独有 API；
  四端环境变量前缀互不兼容且都是编译期替换，共享包写死任何一种，另外三端拿到的是
  undefined 而不是报错；源码直出的包在每个 app 都要单独配 transpile，漏配的报错
  指向包内文件、看着像包坏了。
  预设 pnpm workspace + 源码直出的内部包（不预编译）。
---

# 前端 monorepo

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

以下是 TypeScript／React 多端工作区的示例，名称、目录根与交付边界以项目地图为准：

| app | 框架 | 说明 |
|---|---|---|
| `site` | Next.js（App Router） | 官网与公开协议 |
| `admin` | Vite + React + shadcn | 运营后台，独立部署，**永不进任何客户端包** |
| `client` | Taro 4 + React | **只出微信小程序，不出 H5** |
| `mobile` | React Native + Expo | iOS / Android / Web 用户应用 |

```
ui/
├── package.json
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
├── node_modules/   pnpm 安装生成，不提交
├── apps/{site,admin,client,mobile}
└── packages/
    ├── core/      纯逻辑：domain 类型 / 业务规则 / 纯工具　【禁宿主 API】
    ├── api/       OpenAPI codegen 产物 + 请求封装 + queryClient 默认配置
    ├── tokens/    design token
    ├── ui-web/    DOM 宿主组件（site + admin 共用）
    ├── platform/  跨宿主能力**接口**，实现在各 app
    └── config/    tsconfig / eslint 共享配置
```

共享包与应用归属于同一个前端工作区；工作区位于仓库根或前端子目录，由项目声明。

---

## 按项目交付物裁剪

官网、用户 Web、运营后台、小程序与原生应用是否存在，以及用户 Web 由 Next.js 或 Expo 承载，
均由项目地图声明。删除实际不需要的交付物和只被它使用的依赖，保留其他端仍在使用的共享包。
运营后台独立于用户应用；不为假想平台能力提前造抽象。

---

## packages 准入判据

放进共享包前，三条都要过：

1. **至少三个宿主真的都需要**——不是"以后可能需要"
2. **三端语义能统一在同一个签名下**，不需要给某一端开后门参数
3. **调用方不需要知道自己跑在哪个宿主上**

判据②最容易糊弄过去。举两个真实的反例：

- **业务导航**（`go.home()` / `go.login()`）看着能统一，实际不行：Next 是 `useRouter`、
  Taro 是 `Taro.navigateTo`、RN 是 `navigation.navigate`，而且路径 / 页面栈 / screen
  名的概念各不相同。强行统一等于每端维护一份映射表，比各写各的更难维护。
  正确做法是**方法名对齐、各端各自实现**。
- **通用键值存储**同样不行：浏览器 `localStorage` 与小程序 `Taro.getStorageSync` 是同步的，
  而 React Native 的 `AsyncStorage` 是**异步**的。统一接口要么被迫全异步（浏览器端凭空
  多一层 await），要么 RN 实现不了。窄接口（只存一个布尔标志）反而能同步。

单宿主专有的能力就留在那个 app 里，不要为了"对称"造一个恒 no-op 的实现——那会让读代码
的人以为另外几端也有这个能力。

---

## 依赖方向

```
apps/*  ──> packages/{api, ui-web, platform, tokens, core}
             api ──> core
             ui-web ──> core, tokens
```

- **`core` 不依赖任何包**，也不依赖 React
- **app 之间不能互相 import**，跨 app 复用一律走 `packages/*`
- **feature 之间不能互相 import**，共用部分提到该 app 的 `shared/`

后两条用 eslint `no-restricted-imports` 钉死，不靠自觉。

### `core` 的红线

禁止 `window` / `document` / `localStorage` / `navigator` / `location` / `history`，
禁止 import 任何框架路由与原生 SDK。

宿主从 2 个变成 4 个之后，这条必须从注释升级成**工具强制**：一处违规会在三端炸，
而 TypeScript 编译期完全不报错——小程序没有 `document`，RN 没有 `window`，都是运行时
才发现。

两道防线一起上：

1. `core` 的 tsconfig **不给 DOM lib**（只有 ES2023）——写 `document.x` 直接是类型错误
2. eslint `no-restricted-globals`（内置规则，不需要插件）

第一道更早、更便宜；第二道兜住类型层面看不出的（比如 `globalThis.window`）。

---

## ★ React 18 与 19 必然并存

| app | React |
|---|---|
| `site`（Next 16） | 19 |
| `mobile`（Expo 57） | 19 |
| `admin`（Vite） | 19 |
| `client`（**Taro 4**） | **18** |

Taro 4 的 peerDependencies 锁 `react: ^18`，官方文档也只到 18。这不是能协调的，只能承认。

因此：

- `packages/*` 里任何带 React 的包，peer 一律写 `"^18 || ^19"`
- **不得使用 React 19 独有 API**（`use()`、新版 `useFormStatus` 等）

第二条没有工具能拦：Taro 端编译期不报错，只在小程序运行时炸。写共享包时自己把住。

例外是 `ui-web`——它明确只服务 DOM 宿主（site + admin），peer 直接写 `^19` 更诚实。
小程序和 RN 用不了它的任何东西，它们没有 `div`。

---

## 源码直出：取舍与代价

内部包的 `exports` 直接指向 `.ts` 源码，不预编译。

**好处**：改了立即生效、类型直通、没有构建步骤要维护、没有产物与源码不同步的问题。

**代价**：每个 app 都要单独告诉自己的打包器"这些包要转译"。

| app | 配置 |
|---|---|
| `site` | `next.config.ts` 的 `transpilePackages: ['@myapp/api', ...]` |
| `client` | `config/index.ts` 里 webpackChain 把 workspace 包加进 babel 的 include，**并从 prebundle 排除** |
| `mobile` | Expo SDK 52+ 自动检测 monorepo；**嵌套结构要显式写 metro.config.js** |
| `admin` | Vite 默认转译 workspace 链接的源码，无需额外配置 |

漏配的报错形态是 `Unexpected token`，指向共享包里的某个 `.ts` 文件——看着像那个包坏了，
实际是当前 app 的转译配置没覆盖它。**新增 `@myapp/*` 包时记得回去加一行。**

Taro 那条尤其隐蔽：它默认不编译 `node_modules`，而 pnpm 把 workspace 包**链接进**
`node_modules`，于是源码包正好落在默认不编译的范围里。

---

## ★ 环境变量：共享包不许读

四端机制互不兼容，且**都是编译期替换**：

| app | 前缀 |
|---|---|
| `site` | `NEXT_PUBLIC_` |
| `admin` | `VITE_` |
| `client` | `TARO_APP_` |
| `mobile` | `EXPO_PUBLIC_` |

共享包写死任何一种，另外三端拿到的是 `undefined` 而**不是报错**——请求会静默打到错误的
地址，表现为一片 404，排查方向完全错。

所以：**共享包不读环境变量，改由各 app 在启动时注入。**

```ts
// packages/api
export interface ApiRuntimeConfig {
  baseUrl: string
  isDev: boolean
  fetchImpl?: typeof fetch   // 小程序必须传，那边没有标准 fetch
  onSessionExpired?: () => void
}
export function configureApi(config: ApiRuntimeConfig): void
```

未初始化时**直接抛错**，不要给默认值：静默用空 baseUrl 会让请求打到当前域，
表现为一堆 404 而不是"忘了初始化"。

这个模式顺带解开了另一处耦合：会话失效时共享包只发信号（`onSessionExpired`），
各端自己决定动作——site 广播给其他标签页，mobile 清本地态回登录栈，client 跳登录页。

---

## ★★ 小程序的两个硬约束

**没有标准 `fetch`**，只有 `Taro.request`。所以取数实现必须可注入。

**连 `Response` 构造函数都没有。** 适配器只能构造鸭子类型对象，实现调用方实际用到的
成员，末尾 `as unknown as Response`。这不是偷懒，是唯一可行的做法——但它有代价：

> 共享包哪天用了 `Response` 的其他成员（`.text()`、`.blob()`），小程序端会在**运行时**
> 报 "not a function"，编译期抓不到。**改共享包的请求封装时，要回去看小程序的适配器
> 还够不够。**

把这句话写进适配器文件的注释里，比指望人记得住有效。

---

## 验证

每个包和 app 都要能独立验证：

```bash
cd ui/packages/<pkg> && pnpm exec tsc --noEmit -p tsconfig.json && pnpm exec vitest run
cd ui/apps/site      && pnpm exec next build     # 含 TS 检查，且能查出漏标 'use client'
cd ui/apps/admin     && pnpm exec tsc --noEmit -p tsconfig.app.json && pnpm exec tsc --noEmit -p tsconfig.test.json
cd ui/apps/client    && pnpm exec tsc --noEmit -p tsconfig.json
cd ui/apps/mobile    && pnpm exec tsc --noEmit
```

**单测与 build 互补，都要跑**：vitest 走 esbuild，测不出"漏标 `'use client'`"；
`next build` 测不出运行时逻辑。

pre-commit 的 hook 正则要跟着目录走——**匹配不到文件的 hook 不会报错，它只是永远不执行**。
改完用 `pre-commit run --all-files` 确认每条都真的跑过。

---
