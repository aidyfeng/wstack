---
name: standard-taro-miniprogram
description: >
  Taro 微信小程序规范——只出小程序不出 H5、条件编译的边界、包体积上限、
  与 App 端的同构约定、小程序特有的身份与支付限制。写小程序页面 / 组件、
  接微信能力、调编译配置、排查包体积时使用。
  几条只有小程序才有的硬约束：主包 2MB、总包 20MB，超了直接发布不了；
  没有标准 fetch，连 Response 构造函数都没有；React 锁在 18（Taro 4 的 peer）；
  iOS 端小程序不允许虚拟商品支付，这是审核红线不是技术限制。
  身份上一条不可逆的坑：微信侧要用 unionid 而非 openid 作稳定标识，选错之后
  同一个人在不同端会被认成不同用户，事后无法程序化修复。
  预设 Taro 4 + React + pnpm workspace 共享包。
---

# Taro 微信小程序

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

## ★ 只出小程序，不出 H5

Taro 能编译到 H5，**但不要用这条路白送一个网页版**。

小程序天生是手机端单一形态：`rpx` 按 750px 基准换算、没有响应式概念、布局按单列手机
排。编译到 H5 后在桌面上只能做成"手机形状居中"的大手机。

网页版归 Next.js 站点做真正的响应式。这两件事看着重叠，实际前提完全不同。

---

## ★★ 条件编译只允许出现在 platform 层

原则一句话：**UI 不分叉，能力分叉。**

`process.env.TARO_ENV` 判断与 `.weapp.tsx` 文件后缀**只允许出现在 `platform/` 目录下**，
feature 代码里出现即打回。

理由和"平台判断集中在一处"是同一条，只是在多宿主下后果更重：判断散落之后，想知道
"这个功能在小程序上到底走哪条路"就得全局搜索，而搜索结果里还混着 UI 分支和能力分支。

---

## ★ 与 App 端的 features 保持同构

小程序与 RN App 的 `features/` 要**同名、同结构**：一样的 feature 名，一样的
`hooks/` / `services/` / `components/` 划分。

配套的硬约束：**`hooks/` 与 `services/` 必须宿主无关**——不许 import `@tarojs/components`，
需要 Taro API 时一律经 `platform/`。

守住这条，两端的差异就只剩组件层。价值不只是"对照着改成本低"：小程序里的
`hooks/`+`services/` 本来就是纯 React + React Query + 请求封装，**在普通 React 里能直接跑**。
将来要调整端的分工（比如把某个功能挪到网页版），重写的只是组件层，业务逻辑整层平移。

---

## 取数：没有标准 fetch

小程序只有 `Taro.request`。所以共享 api 包的取数实现必须可注入，本端提供适配器。

**更麻烦的是：连 `Response` 构造函数都没有。** 适配器只能返回鸭子类型对象，实现调用方
实际用到的那几个成员（`json()` / `ok` / `status` / `headers.get()`），末尾
`as unknown as Response`。

这个 cast 是有意的，但要在适配器文件顶部写清楚代价：

> 共享包哪天用了 `Response` 的其他成员（`.text()`、`.blob()`），小程序端会在**运行时**
> 报 "not a function"，编译期抓不到。改共享包的请求封装时，回来看这个适配器还够不够。

会话也不同：小程序的 cookie 机制与浏览器不一样（`Taro.request` 不自动带 cookie），
`credentials: 'include'` 那套在这边不成立。接真实登录时要决定是改用 header 传会话标识，
还是手工维护 cookie。

---

## ★★ 环境变量必须在 defineConstants 里登记

小程序**没有 `process` 全局**。Taro 的 DefinePlugin 会把 `process.env.XXX` 在编译期替换成
字面量，但它只替换**自己知道值的**变量——`NODE_ENV` 它会设，而 `TARO_APP_*` 只有在 `.env`
里定义过才会被替换。

没被替换的那个会原样留在产物里，于是小程序一启动就：

```
ReferenceError: process is not defined
Page "pages/index/index" has not been registered yet.
```

第二行是连带后果（`app.js` 执行中断，页面注册没跑到），**看不出根因**，很容易往路由配置
那边查。

所以：在 `config/index.ts` 的 `defineConstants` 里**逐个登记**并给默认值，
保证任何情况下都是编译期字面量：

```ts
defineConstants: {
  'process.env.TARO_APP_API_BASE_URL': JSON.stringify(
    process.env.TARO_APP_API_BASE_URL ?? '',
  ),
},
```

新增 `TARO_APP_*` 变量时记得回来加一行。**验证方法**：编译后
`grep -c 'process\.' dist/*.js` 必须是 0。

（这条只有真机/开发者工具才会暴露：typecheck 和编译都不报错，产物也正常产出。）

---

## React 版本锁在 18

Taro 4 的 peerDependencies 是 `react: ^18`，官方文档也只到 18。而 Next 与 Expo 用 19。

所以共享包必须 `"^18 || ^19"` 双版本兼容，且**不得使用 React 19 独有 API**——
用了在这边编译期不报错，只在小程序运行时炸。

---

## 包体积：主包 2MB / 总包 20MB

微信的硬上限，超了**发布不了**（不是警告，是拒绝）。

- 首页与登录流程放主包，其余按业务域分包
- 图片一律走 CDN，不进包
- 引第三方库前先看体积，小程序里一个 moment.js 就能吃掉主包的一大块
- 定期跑体积分析，不要等发布被拒才查

分包加载有首次进入的延迟，所以分包边界要按"用户动线"切，不是按代码目录切。

---

## designWidth 与 rpx

`designWidth: 750` 是微信小程序的标准基准，设计稿按 750 出，`rpx` 直接换算。

改这个值会让所有既有样式一起偏，**项目开始时定死，之后不要动**。

---

## ★ 身份：用 unionid，不要用 openid

微信的 `openid` 是**每个应用各自不同**的：同一个人在小程序、公众号、App 里拿到三个
不同的 openid。`unionid` 才是同一开放平台账号下的稳定标识。

选错的后果不可逆：同一个人在不同端被认成不同用户，数据分裂，**事后无法程序化合并**，
只能人工申诉一个个处理。

在国内语境下还有一条立场：所有登录方式最终都要归到一个已验证的手机号。小程序内微信
身份是隐式的，但涉及跨端时仍要落到手机号上，否则同一个人从不同入口进来会分裂成多个
互不相通的账号。

---

## ★ iOS 端不允许虚拟商品支付

这是**审核红线，不是技术限制**：iOS 上的小程序不能通过任何方式售卖虚拟商品
（会员、点数、解锁内容）。绕开的写法（跳外链、二维码、客服引导）同样会被拒。

设计付费功能时，iOS 侧的小程序只能做展示与说明，实际购买引导到 App（走 Apple 内购）
或安卓端。**这条要在做产品设计时就算进去**，不是接支付时才发现。

---

## monorepo 集成

Taro **默认不编译 `node_modules`**，而 pnpm 把 workspace 包链接进 `node_modules`——
源码直出的共享包正好落在默认不编译的范围里。

必须两件事一起做：

1. webpackChain 把 workspace 包目录加进 babel 的 `include`
2. 从 `prebundle.exclude` 里排除这些包（预打包会按成品包处理，拿到未编译的 TS）

漏了的报错是 `Unexpected token`，指向共享包里的 `.ts` 文件——看着像那个包坏了。

---
