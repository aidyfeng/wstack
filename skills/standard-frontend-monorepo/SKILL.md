---
name: standard-frontend-monorepo
description: >
  前端 monorepo 包边界。决定代码放进共享包还是留在 app，或把 app 接到源码直出的共享包（转译与运行时注入）时使用。
---

# 前端 monorepo

各 app 承载哪些页面见 `skills/wayne-mode/playbooks/frontend.md`。本篇只定包边界。

共享包和 app 在同一个 pnpm workspace（仓库根或前端子目录）。内部包源码直出，不预编译。`node_modules/` 由 pnpm 安装生成，不提交。

```
ui/
├── package.json
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
├── apps/{site,admin,client,mobile}
└── packages/
    ├── core/      纯逻辑：domain 类型 / 业务规则 / 纯工具。无宿主 API
    ├── api/       OpenAPI codegen 产物 + 请求封装 + queryClient 默认配置
    ├── tokens/    design token
    ├── ui-web/    DOM 宿主组件（site 与 admin）
    ├── platform/  跨宿主能力的接口，实现写在各 app
    └── config/    tsconfig / eslint 共享配置
```

`admin` 独立部署，不打进任何客户端包。`client` 只出微信小程序，不出 H5。

## 共享包准入

三条都过才放进共享包：

1. 至少三个宿主现在就要用
2. 三端能收进同一个签名，不为某一端加后门参数
3. 调用方不必知道自己跑在哪个宿主

业务导航（`go.home()` / `go.login()`）过不了第 2 条：Next 是 `useRouter`，Taro 是 `Taro.navigateTo`，RN 是 `navigation.navigate`，路径、页面栈、screen 名各不相同。方法名对齐，各 app 自己实现。

通用键值存储过不了第 2 条：浏览器 `localStorage` 与小程序 `Taro.getStorageSync` 同步，React Native 的 `AsyncStorage` 异步。收成一个接口会逼所有调用方 await，或者 RN 实现不了。只存一个布尔标志这类窄接口可以保持同步。

只在一个宿主存在的能力留在那个 app。为了对称补一个恒 no-op 的实现，会让另外几端看起来也有这个能力。

## 依赖方向

```
apps/*  ──> packages/{api, ui-web, platform, tokens, core}
             api ──> core
             ui-web ──> core, tokens
```

- `core` 不依赖任何包，也不依赖 React
- app 之间不互相 import；跨 app 复用走 `packages/*`
- feature 之间不互相 import；共用部分提到该 app 的 `shared/`

后两条用 eslint `no-restricted-imports` 钉住。

### `core` 不接触宿主

`core` 不出现 `window` / `document` / `localStorage` / `navigator` / `location` / `history`，也不 import 框架路由或原生 SDK。

`core` 的 tsconfig 只给 ES2023，不给 DOM lib，`document.x` 是类型错误。eslint `no-restricted-globals`（内置规则）再挡住 `globalThis.window`。小程序没有 `document`、RN 没有 `window`，TypeScript 默认不报，要到运行时才炸。

## React 18 与 19 并存

| app | React |
|---|---|
| `site`（Next 16） | 19 |
| `mobile`（Expo 57） | 19 |
| `admin`（Vite） | 19 |
| `client`（Taro 4） | 18 |

Taro 4 的 peerDependencies 锁 `react: ^18`，官方文档也只到 18。

带 React 的 `packages/*`，peer 写 `"^18 || ^19"`，并且不用 React 19 独有 API（`use()`、新版 `useFormStatus`）。Taro 编译期不报，小程序运行时才炸。

`ui-web` 只服务 DOM 宿主（site 与 admin），peer 写 `^19`。小程序和 RN 没有 `div`，不用这个包。

## 源码直出

内部包的 `exports` 指向 `.ts` 源码。每个 app 把自己的打包器指到这些包：

| app | 配置 |
|---|---|
| `site` | `next.config.ts` 的 `transpilePackages: ['@myapp/api', ...]` |
| `client` | `config/index.ts` 里 webpackChain 把 workspace 包加进 babel 的 include，并从 prebundle 排除 |
| `mobile` | Expo SDK 52+ 自动检测 monorepo；嵌套结构写明 `metro.config.js` |
| `admin` | Vite 默认转译 workspace 链接的源码 |

漏配的报错是 `Unexpected token`，指向共享包里的 `.ts` 文件。新增 `@myapp/*` 包时，回到每个需要转译的 app 加上该包。

Taro 默认不编译 `node_modules`。pnpm 把 workspace 包链接进 `node_modules`，源码包会落在默认不编译的范围里，所以 client 必须同时改 babel include 和 prebundle。

## 共享包不读环境变量

四端前缀不同，而且都是编译期替换：

| app | 前缀 |
|---|---|
| `site` | `NEXT_PUBLIC_` |
| `admin` | `VITE_` |
| `client` | `TARO_APP_` |
| `mobile` | `EXPO_PUBLIC_` |

共享包写死其中一种，另外三端拿到 `undefined`，请求打到错误地址，表现是 404。各 app 在启动时注入：

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

未调用 `configureApi` 就发请求时直接抛错，不设默认 baseUrl。空 baseUrl 会打到当前域，同样表现为 404。

会话失效时共享包只调用 `onSessionExpired`。site 广播给其他标签页，mobile 清本地态并回到登录栈，client 跳登录页。

## 小程序请求适配

小程序没有标准 `fetch`，只有 `Taro.request`。取数实现经 `fetchImpl` 注入。

小程序没有 `Response` 构造函数。适配器构造调用方实际用到的成员，末尾 `as unknown as Response`。共享包一旦用上未实现的成员（`.text()`、`.blob()`），小程序运行时报 "not a function"，编译期抓不到。改共享包请求封装时，对照适配器已实现的成员；把这份清单写在适配器文件的注释里。

## 验证

```bash
cd ui/packages/<pkg> && pnpm exec tsc --noEmit -p tsconfig.json && pnpm exec vitest run
cd ui/apps/site      && pnpm exec next build     # 含 TS 检查，且能查出漏标 'use client'
cd ui/apps/admin     && pnpm exec tsc --noEmit -p tsconfig.app.json && pnpm exec tsc --noEmit -p tsconfig.test.json
cd ui/apps/client    && pnpm exec tsc --noEmit -p tsconfig.json
cd ui/apps/mobile    && pnpm exec tsc --noEmit
```

vitest 走 esbuild，查不出漏标 `'use client'`；`next build` 查不出运行时逻辑。单测和 build 都跑。

pre-commit 的 hook 正则跟着目录走。匹配不到文件的 hook 不报错，只是从不执行。改完跑 `pre-commit run --all-files`，确认每条都执行过。
