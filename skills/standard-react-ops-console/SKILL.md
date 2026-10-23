---
name: standard-react-ops-console
description: >
  给运营/管理员用的后台前端（React SPA）规范——与面向用户的前端分开部署。写后台列表页、
  编辑弹窗、API 请求层、登录态、多页签、表单、主题映射时使用。
  多数条目防的是**静默失败**：代理配错表现为静默 401（看着像会话失效，其实请求没打到该去的
  后端）、PATCH 整对象回传会静默覆盖别人的改动、多页签不隔离会让隐藏页签跟着执行一遍操作。
  前提：React + React Router + 组件库（shadcn 等）+ 设计 token 层。
---

# 运营后台前端（React SPA）

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

适用前提：

- 后台是**独立 SPA**，与面向用户的前端分开部署（独立域名/子域），不打进移动端包
- 会话走 HttpOnly cookie（不是前端可读的 token）
- 有一层设计 token，组件库的默认 token 被映射到项目语义 token

本篇多数条目防的是**静默失败**：不报错、不红、不告警，只是请求悄悄打错了后端、数据悄悄被
覆盖、操作悄悄在别的页签里也执行了一遍。凡标了「静默」的地方都不能指望"出问题会有人发现"。

---

## 与面向用户端的关键分叉：同源 cookie 会话

后台请求一律走**相对路径** `/api/*`，**不要**拼绝对地址直连后端。这跟面向用户的那个前端
往往是相反的（后者常直连、靠 CORS 放行）——**同一个仓库里两套前端两种做法，是最容易抄错的
一处**。

原因：后台会话是 HttpOnly cookie。生产环境 SPA 与 API 同源，cookie 自然带上；dev 环境靠
devServer 的 proxy 把 `/api` 转发到后端，**模拟同源**以保住这枚 cookie。一旦绕开代理直连，
就成了跨域请求，cookie 带不上，后端判未登录。

```ts
// ✅ 相对路径 + credentials include
fetch(endpoint, { ...init, credentials: 'include' })

// ❌ 拼绝对地址（面向用户端的模式，后台不能抄）
fetch(`${import.meta.env.VITE_API_BASE_URL}/api/v1/admin/...`)
```

**dev 改后端端口只改代理目标那一个变量**——面向用户端那个 baseURL 变量对后台完全无效，
后台根本不读它。

**症状要认得**：配错的表现是**静默 401**——接口通了、返回未登录。它看起来像"会话失效"，
实际是"请求根本没打到该去的地方"。排查第一步是看 Network 里请求的 Origin 是不是本机
devServer（走了代理），而不是某个绝对地址。

---

## API 请求层：单一入口

所有请求走统一封装（`request` / `requestWithMeta` / `uploadFile` 之类），**禁止在页面组件里
手写裸 `fetch` 或自己判 `response.ok`**。

封装内部统一做三件事：

1. **解析响应信封**：`code === 0` 成功；`code !== 0` 或 HTTP 非 2xx 一律抛统一的 `ApiError`
   （带 `code` / `trace_id` / `details`）
2. **网络失败与响应体解析失败也抛同一个 `ApiError`** —— 调用方只需 catch 一种异常
3. **文件上传不手动设 `Content-Type`** —— 交给浏览器带 multipart boundary

**错误码 → 用户文案的映射表集中在一个模块**，逐级回退：

```
命中已知 err.code  →  对应文案
未命中            →  回退后端 message
非 ApiError       →  回退调用方传入的兜底文案
```

```ts
// ✅ catch (e) { setError(messageForApiError(e, '保存失败')) }
// ❌ catch (e) { setError((e as Error).message) }   用户看到英文/技术性文案
```

**新增后端错误码时必须同步往这张表加一行**，否则前端静默漏译，用户看到看不懂的原文。这条
是跨端契约，后端加码时要连带想到前端这张表。

---

## PATCH 语义：只发本次真正要改的字段

更新型接口一律 `PATCH`，请求体**只放这次真正改动的字段**，未改的不出现在 body 里。要清空
可空字段必须**显式传 `null`**，不能靠省略。

```ts
// ✅ 只塞真正改的
await updateItem(key, { label: '新标题' })

// ❌ 整对象回传
await updateItem(key, { ...currentItem, label: '新标题' })
```

**为什么整对象回传是危险的**：漏发字段的后果不是"后端不改它"，而是后端把**缺省值**当成
"用户主动清空"落库。`is_free: false`、`sort_order: 0`、`note: ""` 这类假值字段一旦被整对象
带回去，会静默覆盖掉别人刚改的数据——不报错，只是数据没了。

服务端的判据是"请求体里有没有这个键"，所以前端**少发一个键**和**发一个 `null`** 在服务端是
两种不同语义。服务端侧如何实现这个判据见 `standard-fastapi-ddd-backend`。

同样的原则适用于画布节点属性面板等局部编辑场景：维护一个 `patch(partial)` 闭包只合并变化
字段，不整对象重建后回写。

---

## 多页签 keep-alive

运营后台常需要同时开多个页面对照（比如两个编辑器并排看）。用路由 pathname（不含 search）
做页签唯一键，缓存已打开页面的组件树。

以下三条都是实测踩出来的，缺一条就会出诡异 bug：

**① 非激活页签用 CSS `hidden`，不要用 React `<Activity>`**

```tsx
// ✅
<div className={isActive ? 'h-full' : 'hidden'}>{cache[path]}</div>

// ❌ <Activity mode={isActive ? 'visible' : 'hidden'}>
```

`<Activity>` 在 hidden→visible 时会卸载再重新挂载副作用——每个页面"挂载时 fetch"的 effect
每次切回页签都重跑一遍接口。纯 CSS 隐藏下组件树全程真实挂载，effect 只跑一次，页面内的
debounce 定时器（如自动保存）也不会被隐藏打断。

**② 隐藏页签必须冻结 location**

CSS 隐藏**不会**暂停 `useLocation()` / `useSearchParams()`——它们读的是 router 的全局单一
context。其它页签一导航，隐藏页签内部这些 hook 跟着重新求值，误触发依赖 search 的 effect。
解法是给每个页签存档"最后一次激活时"的 location 值，用 router 的 location context provider
包住该页签的子树。

**③ window 级监听器必须自守**

注册在 `window` 上的键盘监听（Ctrl+V / Delete / Ctrl+Z 等）会被**每个打开着的页签实例**同时
收到。不自守的后果：在一个页签里粘贴，其它所有已打开的同类页签各自也被粘贴了一份。

解法是提供一个"当前页签是否激活"的 context，在处理函数**最开头**判断，非激活直接 return。

---

## 表单状态：不引表单库

编辑弹窗一律裸 `useState` + 手算 `canSubmit`，**不引入** `react-hook-form` / `zod` 等表单校验库。

```ts
// ✅
const canSave = isNew
  ? key.trim() !== '' && type !== '' && label.trim() !== ''
  : label.trim() !== ''
```

理由：后台表单大多字段少、校验是简单的非空/互斥关系，schema 校验框架带来的抽象成本大于收益，
且会让代码风格在仓库里分裂成两套。字段较多时（如"三项要么全填要么全不填"），校验直接写在
`canSubmit` 的布尔表达式或提交前的手动检查里。

**每个编辑弹窗固定再带两个 state**：

- `isSaving` —— 提交中禁用按钮 / 显示 loading
- `error` —— 保存失败时**内联展示**（走上面的 `messageForApiError`），不要用全局 toast 承载
  表单级错误：toast 会飘走，而用户此时正需要对着表单改

**新建/编辑复用同一组件时，在弹窗打开的瞬间重置表单状态**（`useEffect` 依赖 `open`），
而不是让表单字段直接派生自 props——后者会在 props 变化时把用户正在输入的内容冲掉。

---

## 列表页：分页与深链，按场景选写法

两种写法都对，按**是否需要从外部链接直达具体状态**来选，同一页面内不要混：

| 场景 | 写法 |
|---|---|
| 纯翻页浏览，刷新回到第一页可接受 | 局部 `useState` 存页码 |
| 需要深链回到具体页签/条目（从别处跳回、分享给同事） | 写进 URL（`useSearchParams`） |

需要深链的典型是"审计记录里点一条跳到对应编辑器的某个位置"这类跨页面跳转——目标状态必须
能被 URL 完整表达。

---

## 设计 token 映射

组件库（shadcn 等）的默认 token 必须**重定向到项目语义 token**，组件里**禁止硬编码颜色、
禁止现造新 token**。

```css
/* ✅ 组件库输出名 ← 项目语义名 */
@theme inline {
  --color-primary: var(--accent);
  --color-destructive: var(--crisis);
  --color-border: var(--border);
}
```

```tsx
// ❌ <div className="bg-[#f4a261] text-white">
// ✅ <div className="bg-primary text-primary-foreground">
```

- 新增视觉需求先查设计文档有没有对应语义 token，**往映射层加一行**，而不是在组件里现造变量名或裸色值
- 注意组件库的语义名与项目语义名**不一定同名同义**（典型：组件库的 `accent` 常指 hover 底色，
  而项目里的"品牌强调色"可能叫别的）。改之前确认改的是哪一个
- 后台通常只需要一套外观（亮色），不必为深色模式写映射——除非产品明确要求

---
