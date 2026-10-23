---
name: standard-taro-miniprogram
description: >
  Taro 微信小程序。写小程序页面或组件、接微信能力、改编译配置、查包体积时使用。
---

# Taro 微信小程序

小程序是 `ui/apps/client`。适用 Taro 4 + React。

## 编译目标与 designWidth

编译目标是微信小程序。`designWidth: 750`，设计稿按 750 出，样式用 `rpx`，布局按单列手机排。项目开始时就把 `designWidth` 定成 750。之后保持这个值：一改，既有样式一起偏。

Taro 能出 H5。H5 产物没有响应式，在桌面上是按 750 宽度居中的一块手机框。网页版不走这条编译目标。

## 条件编译

`process.env.TARO_ENV` 和 `.weapp.tsx` 只放在 `platform/`。feature 代码里出现，就挪回 `platform/`。UI 用同一套；分叉的是能力。

## 与 App 的 features 同构

小程序和 RN App 的 `features/` 同名、同结构：一样的 feature 名，一样的 `hooks/` / `services/` / `components/`。

`hooks/` 和 `services/` 不 import `@tarojs/components`。Taro API 经 `platform/`。这两层是 React、React Query 和请求封装，在普通 React 环境里能直接跑。

## 取数

小程序的请求 API 是 `Taro.request`。共享 api 包的取数实现做成可注入，本端提供适配器。

运行时没有 `Response` 构造函数。适配器返回鸭子类型，实现调用方实际用到的 `json()`、`ok`、`status`、`headers.get()`，末尾 `as unknown as Response`。

在适配器文件顶部写明代价：共享包一旦用了 `Response` 的其它成员（`.text()`、`.blob()`），小程序会在运行时报 "not a function"，编译期抓不到。改共享包的请求封装时，回来核对这个适配器还盖不盖得住。

`Taro.request` 不自动带 cookie，`credentials: 'include'` 在这里不成立。接真实登录时，用 header 传会话标识，或手工维护 cookie。

## defineConstants

小程序没有 `process` 全局。Taro 的 DefinePlugin 会把自己知道值的 `process.env.XXX` 在编译期换成字面量。`NODE_ENV` 它会设。`TARO_APP_*` 只有在 `.env` 里定义过才会被替换。没被替换的标识符留在产物里，启动就是：

```
ReferenceError: process is not defined
Page "pages/index/index" has not been registered yet.
```

第二行是 `app.js` 执行中断、页面注册没跑到。根因是产物里还留着 `process`。

在 `config/index.ts` 的 `defineConstants` 里逐个登记，并给默认值，保证任何情况下都是编译期字面量：

```ts
defineConstants: {
  'process.env.TARO_APP_API_BASE_URL': JSON.stringify(
    process.env.TARO_APP_API_BASE_URL ?? '',
  ),
},
```

每新增一个 `TARO_APP_*`，这里加一行。编译后 `grep -c 'process\.' dist/*.js` 为 0。typecheck 和编译都不报这条，产物也会正常产出；真机或开发者工具才会暴露。

## React 版本

Taro 4 的 peerDependencies 是 `react: ^18`，官方文档也只到 18。Next 与 Expo 用 19。共享包 peer 写 `"^18 || ^19"`，并且不用 React 19 独有 API。用了的话，小程序编译期不报错，运行时才炸。四端版本对照见 `standard-frontend-monorepo`。

## 包体积

微信上限是主包 2MB、总包 20MB。超过会被拒绝发布。

- 首页和登录流程放主包，其余按业务域分包。
- 图片走 CDN，不打进包。
- 引第三方库之前先看体积。一个 moment.js 就能吃掉主包的一大块。
- 定期做体积分析。

分包第一次进入有延迟。分包边界按用户动线切，不按代码目录切。

## 身份

微信跨应用的稳定标识用 `unionid`。`openid` 每个应用各不相同：同一个人在小程序、公众号、App 里是三个 openid。用 openid 当用户键，同一个人会被认成不同用户；openid 推不出 unionid，不能程序化合并，只能人工处理。

跨端时，登录最终落到一个已验证的手机号。小程序里的微信身份是隐式的，只靠它会把不同入口拆成互不相通的账号。账号模型见 `standard-multi-provider-auth`。

## iOS 虚拟商品

iOS 上的小程序不售卖虚拟商品（会员、点数、解锁内容）。这是审核规则。外链、二维码、客服引导同样会被拒。

iOS 小程序侧只做展示和说明。购买放到 App（Apple 内购）或安卓。做付费设计时就按这个分端。

## monorepo 里的编译

Taro 默认不编译 `node_modules`。pnpm 把 workspace 包链接进 `node_modules`，源码直出的共享包正好落在默认不编译的范围里。两件事一起做：

1. webpackChain 把 workspace 包目录加进 babel 的 `include`。
2. 从 `prebundle.exclude` 里排除这些包。预打包会按成品包处理，拿到的是未编译的 TS。

漏了的报错是 `Unexpected token`，指向共享包里的 `.ts` 文件，看着像那个包坏了。其它 app 的转译配置见 `standard-frontend-monorepo`。
