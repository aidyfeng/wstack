---
name: standard-react-conventions
description: >
  React 约定（四端共用）。写页面、组件、hook、service，调整状态方案，改设计 token，或改业务导航与废弃 URL 时使用。
---

# 四端共用的 React 约定

本篇是四端共用、与宿主无关的写法。宿主差异见 `standard-taro-miniprogram`、`standard-react-native-app`、`standard-react-ops-console`。跨包边界见 `standard-frontend-monorepo`。

预设 React + React Query，无全局 store。

## fallback 只在 DEV 下给

请求封装如果支持失败时返回兜底数据，这个能力只用于本地离线开发。生产路径上失败要抛错，调用方决定怎么呈现。生产里返回兜底会变成假成功：调用方拿到看似正常的数据，不抛错、不告警、不上报。

```ts
// ✅ fallback 显式挂在 DEV 判断后面
fallback: isDev ? { items: [], total: 0 } : undefined,

// ❌ 裸 fallback —— 生产失败时用户看到的是这份编造的数据
fallback: { completed: true, level: 2, badge: '已解锁' },
```

裸 fallback 还会伪造用户成就：用户以为自己升级了，刷新后又没了。

拿不准就不要给 fallback。

埋点、非关键上报这类 fire-and-forget 可以吞错，注释里写明，和掩盖故障分开。

Review 看到没有 DEV 判断的裸 `fallback`，打回。

实现放在共享 api 包，四端共用一份请求封装，不在各 app 各写一遍。`isDev` 由各 app 注入。共享包不读环境变量，见 `standard-frontend-monorepo`。

这条要能被测试钉住。`isDev` 若直接读构建工具的环境变量，测试环境恒为 true，「生产环境 fallback 必须失效」测不了。注入之后才能测。覆盖三条路径：网络失败、非 JSON 响应、业务错。

## 状态：三层

1. **React Query** —— 全部服务端数据
2. **少量 Context** —— 全局横切的客户端态（登录态、无障碍偏好这一类，个位数）
3. **组件局部 `useState`** —— 其余

新的 `createContext` 要说明为什么它不是服务端数据。多数看起来要全局的状态，归 React Query。

Zustand、Redux、Jotai 只在这三层确实不够时再引入。

## React Query

全局默认集中设一次：`staleTime: 60_000`、`retry: 1`、不 `refetchOnWindowFocus`。四端共用同一份默认值，由共享 api 包导出工厂函数，各端不各设一套。

单个 query 偏离默认时，写一句为什么：

```ts
// ✅ 拉长到 5 分钟：预热页与详情页共用同一个 key，要盖住用户走完中间流程的时间窗口
staleTime: 5 * 60 * 1000,

// ✅ 改成 0：这个列表要每次回到首页都最新
staleTime: 0,
```

没有注释的偏离，下一个人既不敢改也不敢删。

`queryKey` 默认写字面量数组（`['state-plan', stateKey]`）。筛选条件多、key 组合复杂时（典型是后台列表页）再抽 `xxxKeys.list()` / `detail()`。提前抽象会让 `invalidateQueries` 的 key 匹配变绕。

跨多个域读写的 key 另算。登录态这种被 auth、settings、membership 都要失效的 key，提到共享 api 包里作为常量导出。散成字面量时，漏一处就是页面数据不刷新。

mutation 成功后失效所有关联 key，不只失效自己：

```ts
onSuccess: () => {
  qc.invalidateQueries({ queryKey: ['states'] })
  qc.invalidateQueries({ queryKey: ['state-plan', stateKey] })
  qc.invalidateQueries({ queryKey: ['my-skills'] })   // ← 漏掉它，首页进度条就不刷新
},
```

写 `onSuccess` 前先列出：这次写会让哪些其他 query 过期。漏一个，页面不报错，数据不刷新。

## API 客户端

认证走 HttpOnly cookie 时，前端拿不到 token，也不存 token。请求统一带凭据，本地存储里不放凭据。

401 触发一次刷新重试，并发请求共享同一个刷新 Promise：

```ts
if (err instanceof ApiError && err.code === UNAUTHORIZED) {
  if (refreshRetry < 1) {
    await refreshSession()        // 多个并发 401 共享同一个 Promise，去重防雪崩
    return _innerRequest(endpoint, options, refreshRetry + 1)
  }
  onSessionExpired?.()            // 重试后仍失败才通知上层
}
```

不去重时，一个页面十个请求同时 401，会打十次刷新。刷新接口通常还带轮转，互相把对方的新 token 作废。

会话彻底失效时只发信号，不做跳转。共享包不知道失效之后该去哪。浏览器要广播给其他标签页，App 要清本地态回到登录栈，小程序直接跳登录页。用回调把决定权交回各端。

写用户状态、进度、成就的接口走带认证的请求函数，不走匿名版本。

## 组件目录

```
features/{feature}/
├── components/  hooks/  services/  types.ts  index.ts
```

| 类型 | 命名 |
|---|---|
| 组件文件 | `PascalCase.tsx` |
| Hook | `use{Name}.ts` |
| API service | `{feature}-api.ts` |

`components/` 不知道用户是谁，也不知道这是哪个业务对象：纯 UI 原语、布局壳、设计系统组件。`shared/` 跨 feature 复用，但懂业务概念（登录守卫、按业务 key 查数据的 hook）。

放哪个目录，看它要不要知道业务概念。

同一把尺子往上一层：不带业务语义、且 DOM 宿主通用的 UI 原语进共享 ui-web 包；不带宿主耦合的纯逻辑进 core 包。包的准入和依赖方向见 `standard-frontend-monorepo`。

feature 之间要复用，把共用部分提到 `shared/`。互相 import 会让两个 feature 拆不开。这条用 eslint 钉死，见 `standard-frontend-monorepo`。

Barrel 逐个具名列出，不用 `export *`。这个 feature 对外暴露了什么一眼能查，也利于 tree-shaking。

## features 的 hooks / services 与宿主无关

`features/<name>/hooks/` 和 `services/` 不 import 宿主专有模块（框架路由、`@tarojs/components`、`react-native`）。宿主能力经 platform 层。

这样 hooks 和 services 只依赖 React、React Query 和请求封装，换一端可以直接跑。跨端要改的是组件，业务逻辑整层平移。

组件按宿主的交互习惯写，不要求四端同一份组件。原则：UI 不分叉，能力分叉。

## 路由按端分叉

四端的路由机制不同，各写各的：

| 端 | 机制 |
|---|---|
| site | Next 文件路由 + route group |
| admin | React Router，路由集中在单文件、顶部注释维护分组 |
| client | Taro 的 `app.config.ts` pages 数组 |
| mobile | Expo Router 文件路由 |

业务导航收进一层封装（`useGo()` 一类）。`features/*` 调这层，不直接调各端导航 API。路径改名只改一处。各端各自实现，方法名对齐，不放进共享包。原因见 `standard-frontend-monorepo` 的准入判据②。

有 URL 的端（site、admin）用重定向接住废弃 URL。App 端的对应问题是 deep link。直接删旧路径会让书签、外链和浏览器历史 404。

## 设计 Token

视觉取值先读项目的设计真理源。

Token 单向落地：设计文档 → token 包 → 各端按自己的形式消费。先写代码再补文档，真理源会分裂。

四端消费形式不同：CSS 变量（site、admin）、SCSS（小程序）、TS 对象（RN）、Tailwind theme。真理源用与形式无关的数据（JSON），生成脚本产出四份产物。小程序和 RN 读不了 CSS 自定义属性。

分清内容语境和主题。有些页面天生是暗的（沉浸式播放、睡前场景），那是内容本身的样子，不是用户可切换的皮肤。容器套 `data-surface="night"` 一类属性，容器内的文字、描边、强调色改走该组变量。

判定为内容语境，三条都要成立：没有 toggle、不跟随 `prefers-color-scheme`、配图不分叉（只维护一份）。

暗底容器内的文字显式套那组变量。沿用亮色 `--text` 就是深底深字，看不清，浅色开发环境下发现不了。

颜色走 token，不写死 hex。token 的名字保持不变（各处引用靠名字对上），只改值。
