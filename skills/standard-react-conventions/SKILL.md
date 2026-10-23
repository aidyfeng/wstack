---
name: standard-react-conventions
description: >
  四端通用的 React 约定——状态管理分层、React Query 用法、API 客户端、组件与目录
  边界、barrel 导出。写页面 / 组件 / hook / service，或调状态方案时使用，
  site / admin / client / mobile 四端**同等适用**。
  框架相关的部分各有专篇：standard-taro-miniprogram（小程序）、
  standard-react-native-app（App，含网页版）、standard-react-ops-console（后台），
  跨包边界见 standard-frontend-monorepo。
  多数条目防的是**静默失败**——不报错、不红、页面看着正常，只是数据是假的或没刷新：
  请求失败时给 fallback 假数据会在生产伪造成功（只能 DEV 下给）；mutation 只失效
  自己的 queryKey 会让别的页面数据不刷新；单个 query 偏离全局默认却不写理由，
  下一个人既不敢改也不敢删。
  预设 React + React Query，**无全局 store**（不用 Zustand / Redux / Jotai）。
---

# 四端通用的 React 约定

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

本篇只放**与宿主无关**的条款。凡是"在 Next 里怎么做 / 在小程序里怎么做"的，
去各端专篇。

---

## ★★ 红线：`fallback` 假数据只能在 DEV 下给

请求封装若支持"失败时返回兜底数据"，这个能力**只能用于本地离线开发**。生产路径上它
会把失败变成**假成功**——调用方拿到看似正常的数据，不抛错、不告警、不上报。

```ts
// ✅ fallback 显式挂在 DEV 判断后面
fallback: isDev ? { items: [], total: 0 } : undefined,

// ❌ 裸 fallback —— 生产失败时用户看到的是这份编造的数据
fallback: { completed: true, level: 2, badge: '已解锁' },
```

第二个例子的危害不止"数据不对"：它伪造了**用户成就**。用户以为自己升级了，刷新后又没了。

- 不确定该不该给 fallback 时，**默认不给**——失败就抛错，让调用方决定怎么呈现
- fire-and-forget 类接口（埋点、非关键上报）可以静默吞错，但要在注释写明，
  与"掩盖故障"区分开
- Review 时看到没有 DEV 判断包裹的裸 `fallback`，直接打回

**这条的实现位置在共享 api 包**（四端共用一份请求封装），不要在各 app 里各写一遍。
判断 DEV 的值由各 app 注入——共享包不读环境变量，理由见 standard-frontend-monorepo。

★ 这条红线要**能被测试钉住**。`isDev` 如果直接从构建工具的环境变量读，测试环境恒为
true，"生产环境 fallback 必须失效"这条根本测不了。改成注入之后才测得了——
覆盖网络失败 / 非 JSON 响应 / 业务错三条路径。

---

## 状态管理：三层，没有全局 store

1. **React Query** —— 所有服务端数据
2. **少量 Context** —— 全局横切的客户端态（登录态、无障碍偏好这类，个位数）
3. **组件局部 `useState`** —— 其余一切

新增全局 Context 前先反问：**这个状态是不是应该由 React Query 管的服务端数据？**
绝大多数"看起来需要全局"的需求答案是"是"。PR 里出现新的 `createContext`，
视为需要额外说明理由的信号，不是默认选项。

同理，想引入 Zustand / Redux 前，先确认现有方案哪里真的不够用。

---

## React Query 约定

**全局默认集中设一次**（典型：`staleTime: 60_000` / `retry: 1` / 不 `refetchOnWindowFocus`）。
四端共用同一份默认值——放在共享 api 包里导出一个工厂函数，而不是各端各设一套。

**单个 query 偏离默认时，必须写一句为什么：**

```ts
// ✅ 拉长到 5 分钟：预热页与详情页共用同一个 key，要盖住用户走完中间流程的时间窗口
staleTime: 5 * 60 * 1000,

// ✅ 改成 0：这个列表要每次回到首页都最新
staleTime: 0,
```

没有注释的偏离，下一个人不敢改也不敢删。

**`queryKey` 默认写字面量数组**（`['state-plan', stateKey]`）。只有筛选条件多、key 组合
复杂的场景（典型是后台列表页）才值得抽 `xxxKeys.list()/detail()` 工厂——提前抽象会让
`invalidateQueries` 的 key 匹配变绕。

**跨多个域读写的 key 例外**：像登录态这种被 auth / settings / membership 都要失效的 key，
提到共享 api 包里作为常量导出。散落成字面量的话，漏掉一处就是一个"页面数据不刷新"的 bug。

**mutation 成功后要失效所有关联 key，不只失效自己：**

```ts
onSuccess: () => {
  qc.invalidateQueries({ queryKey: ['states'] })
  qc.invalidateQueries({ queryKey: ['state-plan', stateKey] })
  qc.invalidateQueries({ queryKey: ['my-skills'] })   // ← 漏掉它，首页进度条就不刷新
},
```

写 `onSuccess` 前先列清楚：这次写操作会让**哪些其他** query 的数据过期？
漏一个就是一个"页面数据不刷新"的 bug，而且页面本身不报错，得靠用户发现。

---

## API 客户端

**认证走 HttpOnly cookie 时，前端拿不到也不存 token**——请求统一带凭据，
不要往本地存储塞任何凭据。

**401 触发一次刷新重试，且并发请求共享同一个刷新 Promise：**

```ts
if (err instanceof ApiError && err.code === UNAUTHORIZED) {
  if (refreshRetry < 1) {
    await refreshSession()        // 多个并发 401 共享同一个 Promise，去重防雪崩
    return _innerRequest(endpoint, options, refreshRetry + 1)
  }
  onSessionExpired?.()            // 重试后仍失败才通知上层
}
```

不去重的话，一个页面十个请求同时 401，会打十次刷新接口——刷新接口通常还带轮转，
互相把对方的新 token 作废。

**会话彻底失效时只发信号，不做动作。** 共享包不该知道"失效之后该跳哪"——
各端处理方式不同（浏览器要广播给其他标签页，App 要清本地态回登录栈，小程序直接跳
登录页）。用回调把决定权交回各端。

写用户状态 / 进度 / 成就的接口一律走带认证的请求函数，不要走匿名版本。

---

## 组件结构与目录边界

```
features/{feature}/
├── components/  hooks/  services/  types.ts  index.ts
```

| 类型 | 命名 |
|---|---|
| 组件文件 | `PascalCase.tsx` |
| Hook | `use{Name}.ts` |
| API service | `{feature}-api.ts` |

**`shared/` 与 `components/` 的分界是「是否绑定业务领域」**：

- `components/` —— 不知道"用户是谁""这是哪个业务对象"。纯 UI 原语、布局壳、设计系统组件
- `shared/` —— 跨 feature 复用，但懂业务概念（登录守卫、按业务 key 查数据的 hook）

放哪个目录，就问一句：**它需要知道业务概念吗？**

同一把尺子往上量一层，就决定了什么该进跨端共享包：不带业务语义、且 DOM 宿主通用的
UI 原语进共享 ui-web 包；不带宿主耦合的纯逻辑进 core 包。

**feature 之间不能互相 import。** 要复用就把共用部分提到 `shared/`——横向 import 会让
两个 feature 再也拆不开。这条用 eslint 钉死，不靠自觉。

**Barrel export 手动逐个具名列出**，不用 `export *`：让"这个 feature 对外暴露了什么"
一眼可查，也利于 tree-shaking。

---

## ★ features 的 hooks / services 必须宿主无关

`features/<name>/hooks/` 与 `services/` 里**不许 import 任何宿主专有模块**
（框架路由、`@tarojs/components`、`react-native`）。需要宿主能力时经 platform 层。

价值不只是整洁：守住这条，`hooks/` + `services/` 就是纯 React + React Query + 请求封装，
**在另一端能直接跑**。跨端差异只剩组件层，将来调整端的分工时，重写的只是组件，
业务逻辑整层平移。

组件层不强求跨端一致——UI 本来就该按宿主的交互习惯做。原则一句话：
**UI 不分叉，能力分叉。**

---

## 路由：按端分叉，没有通用写法

四端的路由机制根本不同，不要试图统一：

| 端 | 机制 |
|---|---|
| site | Next 文件路由 + route group |
| admin | React Router，路由集中在单文件、顶部注释维护分组 |
| client | Taro 的 `app.config.ts` pages 数组 |
| mobile | Expo Router 文件路由 |

唯一通用的是**业务导航要集中在一层封装**（`useGo()` 之类），`features/*` 里不直接
调各端的导航 API。路径改名时只改一处。这一层各端各自实现，靠**方法名对齐**，
不要提到共享包里——理由见 standard-frontend-monorepo 的准入判据②。

**废弃 URL 要接住，不直接删。** 有 URL 的端（site / admin）用重定向，
App 端的等价问题是 deep link。直接删掉旧路径会让书签、外链、浏览器历史全部 404。

---

## 设计 Token

**视觉决策前先读项目的设计真理源**，不要凭感觉取值。

**Token 单向落地**：先进设计文档 → 再进 token 包 → 各端按自己的形式消费。
不要反过来先写代码再补文档。

★ **四端消费 token 的形式不同**：CSS 变量（site / admin）、SCSS（小程序）、
TS 对象（RN）、Tailwind theme。所以 token 的真理源应该是**与形式无关的数据**
（JSON），由生成脚本产出四份产物——小程序与 RN 都读不了 CSS 自定义属性。

**分清「内容语境」与「主题」。** 某些页面天生是暗的（沉浸式播放、睡前场景）——
这是**内容本身长什么样**，不是用户可切换的皮肤。这类容器套一个 `data-surface="night"`
之类的属性，容器内的文字 / 描边 / 强调色改走该组变量。

判定是内容语境而非主题，三条都要成立：没有 toggle、不跟随 `prefers-color-scheme`、
配图不分叉（只维护一份）。

暗底容器内的文字必须**显式**套那组变量——沿用亮色 `--text` 就是深底深字，看不清，
而这在浅色开发环境下不会被发现。

- 颜色一律走 token，不写死 hex
- token **名字**不要改（各处引用靠名字对上），只改**值**

---
