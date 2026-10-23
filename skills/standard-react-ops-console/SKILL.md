---
name: standard-react-ops-console
description: >
  运营后台。写与用户应用分开部署的管理端：列表页、编辑弹窗、API 请求层、登录态、多页签、表单或主题映射时使用。
---

# 运营后台

后台是独立 SPA，与面向用户的前端分开部署（独立域名或子域），不打进移动端包。会话走 HttpOnly cookie，不是前端可读的 token。组件库的默认 token 映射到项目语义 token。

前提：React + React Router + 组件库（shadcn 等）+ 设计 token 层。

## 同源 cookie：请求走相对路径

后台请求走相对路径 `/api/*`。生产环境 SPA 与 API 同源，HttpOnly cookie 会带上。dev 靠 devServer 的 proxy 把 `/api` 转发到后端，模拟同源，保住这枚 cookie。

```ts
// ✅ 相对路径 + credentials include
fetch(endpoint, { ...init, credentials: 'include' })

// ❌ 拼绝对地址（面向用户端的模式，后台不能抄）
fetch(`${import.meta.env.VITE_API_BASE_URL}/api/v1/admin/...`)
```

面向用户的前端常常直连后端、靠 CORS 放行。同一个仓库里两套前端是两种做法。后台绕开代理去拼绝对地址，请求变成跨域，cookie 带不上，后端判未登录。

dev 改后端端口，只改代理目标那一个变量。面向用户端的 baseURL 变量后台不读。

配错的表现是静默 401：接口通了，返回未登录。看着像会话失效，实际是请求没打到该去的地方。排查先看 Network 里请求的 Origin 是不是本机 devServer（走了代理），而不是某个绝对地址。

## API 请求层

所有请求走统一封装（`request` / `requestWithMeta` / `uploadFile`）。页面组件不手写裸 `fetch`，也不自己判 `response.ok`。

封装内部做三件事：

1. 解析响应信封：`code === 0` 成功；`code !== 0` 或 HTTP 非 2xx 抛统一的 `ApiError`（带 `code` / `trace_id` / `details`）。
2. 网络失败和响应体解析失败也抛同一个 `ApiError`。调用方只 catch 一种异常。
3. 文件上传不手动设 `Content-Type`，交给浏览器带 multipart boundary。

错误码到用户文案的映射集中在一个模块，逐级回退：

```
命中已知 err.code  →  对应文案
未命中            →  回退后端 message
非 ApiError       →  回退调用方传入的兜底文案
```

```ts
// ✅ catch (e) { setError(messageForApiError(e, '保存失败')) }
// ❌ catch (e) { setError((e as Error).message) }   用户看到英文/技术性文案
```

新增后端错误码时往这张表加一行。漏了就是前端漏译，用户看到看不懂的原文。后端加码时连带改这张表。

## PATCH：只发这次改的字段

更新型接口用 `PATCH`。请求体只放这次真正改动的字段，未改的不出现。清空可空字段要显式传 `null`，不能靠省略。

```ts
// ✅ 只塞真正改的
await updateItem(key, { label: '新标题' })

// ❌ 整对象回传
await updateItem(key, { ...currentItem, label: '新标题' })
```

服务端看的是请求体里有没有这个键。少发一个键，和发一个 `null`，是两种语义。整对象回传时，漏发字段的后果不是「后端不改它」，而是后端把缺省值当成用户主动清空。`is_free: false`、`sort_order: 0`、`note: ""` 这类假值被带回去，会盖掉别人刚改的数据，而且不报错。

服务端如何区分「没传这个键」和「显式 null」，见 `standard-fastapi-ddd-backend`。

画布节点属性面板等局部编辑同样：用 `patch(partial)` 只合并变化字段，不整对象重建后回写。

## 多页签 keep-alive

运营要同时开多个页面对照。页签唯一键用路由 pathname（不含 search），缓存已打开页面的组件树。下面三条缺一条就会出诡异 bug。

**非激活页签用 CSS `hidden`，不用 React `<Activity>`。**

```tsx
// ✅
<div className={isActive ? 'h-full' : 'hidden'}>{cache[path]}</div>

// ❌ <Activity mode={isActive ? 'visible' : 'hidden'}>
```

`<Activity>` 在 hidden→visible 时会卸载再挂载副作用。每个页面「挂载时 fetch」的 effect 每次切回都重打接口。纯 CSS 隐藏下组件树全程挂着，effect 只跑一次，页面内的 debounce 定时器（如自动保存）也不会被隐藏打断。

**隐藏页签冻结 location。** CSS 隐藏不会暂停 `useLocation()` / `useSearchParams()`，它们读的是 router 的全局单一 context。别的页签一导航，隐藏页签里这些 hook 跟着重新求值，依赖 search 的 effect 会误触发。给每个页签存「最后一次激活时」的 location，用 router 的 location context provider 包住该页签的子树。

**window 级监听器自己判断页签是否激活。** 注册在 `window` 上的键盘监听（Ctrl+V、Delete、Ctrl+Z）会被每个打开着的页签实例同时收到。不判断的话，在一个页签里粘贴，其他已打开的同类页签各自也粘贴一份。提供「当前页签是否激活」的 context，处理函数开头就判断，非激活直接 return。

## 表单

编辑弹窗用裸 `useState` 加手算 `canSubmit`。不引入 `react-hook-form` / `zod`。

```ts
// ✅
const canSave = isNew
  ? key.trim() !== '' && type !== '' && label.trim() !== ''
  : label.trim() !== ''
```

后台表单大多字段少，校验是非空或互斥。schema 框架的抽象成本大于收益，还会让仓库里出现两套风格。字段较多时（如三项要么全填要么全不填），校验写在 `canSubmit` 的布尔表达式里，或提交前手动检查。

每个编辑弹窗再带两个 state：

- `isSaving`：提交中禁用按钮，显示 loading
- `error`：保存失败时内联展示，走 `messageForApiError`。表单级错误不用全局 toast，toast 会飘走，用户这时要对着表单改

新建和编辑复用同一组件时，在弹窗打开的瞬间重置表单（`useEffect` 依赖 `open`）。表单字段不直接派生自 props，否则 props 一变，正在输入的内容会被冲掉。

## 列表页

按要不要从外部链接直达具体状态来选，同一页面里不混用：

| 场景 | 写法 |
|---|---|
| 纯翻页浏览，刷新回到第一页可接受 | 局部 `useState` 存页码 |
| 需要深链回到具体页签或条目（从别处跳回、分享给同事） | 写进 URL（`useSearchParams`） |

深链的典型是审计记录里点一条，跳到对应编辑器的某个位置。目标状态要能被 URL 完整表达。

## 设计 token 映射

组件库（shadcn 等）的默认 token 重定向到项目语义 token。组件里用映射后的名字，不写死颜色，不现造 token。

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

新增视觉需求先查设计文档有没有对应语义 token，往映射层加一行。不在组件里现造变量名或裸色值。

组件库的语义名和项目语义名不一定同名同义。组件库的 `accent` 常指 hover 底色，项目里的品牌强调色可能叫别的。改之前确认改的是哪一个。

后台通常只做一套亮色外观。产品明确要求深色时再写深色映射。
