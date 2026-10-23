---
name: standard-websocket-realtime
description: >
  WebSocket 实时通信规范——单连接+频道订阅、消息信封与频道命名、心跳与断线重连、订阅引用
  计数、多进程广播、前端 Provider+Hook 分层。做实时推送、聊天、协作编辑、任务状态通知，或
  排查"多副本部署后部分用户收不到推送"时使用。
  最容易漏的两条：单机内存广播在多副本下只有本进程的连接收得到，必须过外部消息总线；进程
  既发布又订阅同一总线会收到自己发的消息，需按发布者去重。
  心跳间隔与超时秒数是起点不是定论，按目标系统的网络状况实测调整。
---

# WebSocket 实时通信规范

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

- 需要服务端主动推送（聊天、任务状态变化、协作场景），REST 轮询延迟不可接受
- 服务端多进程/多副本部署（否则「多进程广播」一节可跳过，单进程内广播用内存事件总线即可）

---

## 架构：单连接 + 频道订阅，而非每个功能各开一条连接

每个客户端只建立**一条** WebSocket 连接，通过频道（channel）订阅区分不同业务的消息流，
不要为每个功能单独开一条连接。

理由：每条连接都要单独走一遍认证、心跳、重连生命周期，开销随功能数线性增长；单连接 +
订阅把连接管理收敛到一处，服务端只需维护一套连接状态机。

```
ws(s)://{host}/ws?token={jwt_token}       # 认证用户
ws(s)://{host}/ws?anonymous_id={anon_id}  # 匿名用户
```

频道命名统一用 `{业务前缀}` 或 `{业务前缀}:{id}` 两种形态，同一套命名规则贯穿前端、服务端
与广播层（见下文「多进程广播」）：

| 频道类型 | 格式 | 示例 |
|---|---|---|
| 全局静态频道（无 ID） | `{prefix}` | `tasks` |
| 按分组 ID | `{prefix}:{id}` | `tenant:01ARZ3NDEK...` |
| 按资源 ID | `{prefix}:{id}` | `conversation:01ARZ3NDEK...` |

---

## 消息信封固定结构，不要让 payload 形状随事件类型漂移

客户端 → 服务端固定 `type` 字段驱动分支：

```json
{"type": "subscribe", "channel": "conversation:xxx"}
{"type": "unsubscribe", "channel": "conversation:xxx"}
{"type": "ping"}
{"type": "message", "channel": "conversation:xxx", "content": "Hello", "client_message_id": "uuid"}
```

服务端 → 客户端固定四字段信封，`payload` 内部结构可以按 `event` 变化，但外层信封不变：

```json
{
  "channel": "conversation:xxx",
  "event": "message",
  "payload": {"id": "msg_123", "role": "human", "content": "..."},
  "timestamp": "2025-01-29T10:30:00Z"
}
```

系统控制消息（订阅确认、心跳应答、错误）走独立的 `type` 而不是塞进业务信封：

```json
{"type": "subscribed", "channel": "conversation:xxx"}
{"type": "unsubscribed", "channel": "conversation:xxx"}
{"type": "pong"}
{"type": "error", "message": "..."}
```

**反面**：如果没有固定信封，前端每加一个新 `event` 类型都要单独写一套解析分支，未知
`event` 容易被静默漏处理而不报错。

---

## 心跳、空闲超时与语义化关闭码

双方都要有心跳，服务端要有主动清扫空闲连接的循环——不要指望 TCP keepalive 替代应用层
心跳，反向代理 / NAT 会在应用层无感知的情况下按自己的策略判定连接死掉，时机不受你控制。

- 客户端周期发送 `{"type": "ping"}`，服务端回 `{"type": "pong"}`
- 每收到任意消息都更新该连接的"最后活跃时间"（不限于 ping）
- 服务端周期性扫描超过阈值未活跃的连接，主动 `close` 并带上专属关闭码
- 认证用户与匿名用户可以配不同的超时阈值——匿名连接资源占用应更保守

自定义关闭码要落在 **4000–4999**（WebSocket 协议为应用层保留的区间），不要占用
1000–2999 的协议保留段。关闭码语义化的价值：排查连接异常时客户端能直接从关闭码判断
原因（超时 / 认证失败 / 缺参数），不用回查服务端日志。

| 码（占位，按新项目分配） | 含义 |
|---|---|
| 4000 | 空闲超时 |
| 4001 | Token 无效 |
| 4003 | 缺少认证参数 |

---

## 断线重连与订阅状态必须一起恢复

客户端断线后走固定延迟重连（简单场景不需要一上来就上指数退避），且只在用户仍持有有效
凭证时才重连——正常关闭也可能只是网络切换（如移动网络切到 WiFi），不代表用户主动退出：

```typescript
ws.onclose = () => {
  reconnectTimer = setTimeout(() => connect(), 5000);  // 固定延迟，占位值
};
```

**连接状态和订阅状态是两回事**：连接断开时服务端会丢失这条连接持有的订阅关系，重连成功
后必须重新发送当前所有活跃频道的订阅消息——不要以为"连上了"就等于"该收到的消息都会
继续收到"。

---

## 订阅引用计数：多个组件订阅同一频道，只发一次网络消息

场景：同一页面可能有多个组件关心同一个频道（如列表和详情都订阅同一个会话）。如果各自
独立发订阅 / 取消订阅消息，会出现"组件 B 卸载时取消订阅，组件 A 还在用却被退订"的错误。

前端维护频道级引用计数：首次订阅（计数 0→1）才真正发 WebSocket 订阅消息，最后一个取消
订阅（计数 1→0）才真正发取消订阅消息，中间的计数变化只更新本地状态，不产生网络流量。

```typescript
subscribe(channel) {
  const count = refCounts.get(channel) ?? 0;
  refCounts.set(channel, count + 1);
  if (count === 0) send({ type: "subscribe", channel });  // 首次才发送
}

unsubscribe(channel) {
  const count = refCounts.get(channel) ?? 0;
  if (count <= 1) {
    refCounts.delete(channel);
    send({ type: "unsubscribe", channel });  // 最后一个才发送
  } else {
    refCounts.set(channel, count - 1);
  }
}
```

---

## 多进程 / 多副本部署下，广播必须走外部消息总线

这是本篇最容易被漏掉、也最难在开发环境测出来的一条。单机内存广播（进程内维护一个
`Set<Connection>` 直接遍历发送）在只有一个进程时完全正确；一旦水平扩展成多副本 /
多 worker，**同一个频道的订阅者会分散在不同进程里**——A 进程收到的消息只能发给 A 进程
自己持有的连接，B、C 进程上的订阅者永远收不到。这个 bug 单副本开发环境测不出来，只有
多副本部署后才会暴露，且现象是"部分用户收不到推送"而不是报错，很容易被误判成前端 bug。

规则：广播必须经过一个所有进程都能访问的外部消息总线（Redis Pub/Sub 是最常见的选择），
每个进程既是发布者也是订阅者：

```
进程 A（持有连接 X）──publish──→ 消息总线 ──subscribe──→ 进程 B（持有连接 Y）
                                                     → 进程 C（持有连接 Z）
```

外部总线的频道命名与业务频道命名保持同构（加个前缀区分即可），方便按频道排查：

```python
external_channel = f"ws:channel:{channel}"  # 例: ws:channel:conversation:01ARZ3NDEK...
```

发布时提供本地/总线双通道开关，默认两者都发；纯本地场景（如仅通知本进程内的连接）可以
关掉总线发布，减少不必要的往返：

```python
await manager.publish_to_channel(
    channel="conversation:xxx",
    event="message",
    payload={...},
    via_bus=True,  # 默认同时经总线广播；仅需本地分发时传 False
)
```

---

## 发布者自身去重 + manager 用进程级单例

**自身去重**：每个进程启动时生成一个进程级唯一 ID，发布到外部总线的消息附带这个 ID；
订阅回调里如果消息的发布者 ID 等于自己，直接跳过。

原因：进程发布消息时通常**先本地分发一次**（给本进程持有的连接），再发布到外部总线广播
给其它进程；但本进程自己同时也订阅着这条总线频道，会再收到自己刚发的这条消息——不去重
会导致本进程的连接把同一条消息收到两次。

```python
self._publisher_id = uuid.uuid4().hex  # 进程启动时生成一次

# 发布时附带
message = {"event": "...", "payload": {...}, "publisher_id": self._publisher_id}

# 订阅回调里跳过自己发布的
if data.get("publisher_id") == self._publisher_id:
    continue
```

**进程级单例**：管理连接与订阅关系的 manager 用模块级单例 + 懒初始化，不要在多处各自
`new`；总线客户端（如 Redis client）在 manager 内部按需获取，不要在模块导入期建立连接
——导入期通常还没进入事件循环，过早建连会绑定错的 loop。

```python
_manager: ConnectionManager | None = None

def get_connection_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager(bus_client=None)  # 总线客户端延迟获取
    return _manager
```

测试用的重置函数（如 `reset_connection_manager()`）只在测试代码里调用，生产路径不应该
有任何地方主动重建单例。

---

## 频道内二次收窄投递，不要为按需隔离新开频道

有些频道是"全局的"但消息只该发给其中一部分订阅者（比如任务通知频道所有人都订阅，但
每条通知只该推给通知里指名的那个用户）。这种场景不需要为每个用户单独开一条频道（会导致
频道数量随用户数爆炸），而是在广播时按 `payload` 里的字段做二次过滤：

```python
if channel == "tasks" and isinstance(payload.get("user_id"), str):
    recipients = identity_connections.get(payload["user_id"], set())
else:
    recipients = channel_subscribers.get(channel, set())
```

---

## 前端分层：Provider 管连接，Hook 管订阅，发布订阅解耦组件通信

一个 Provider 对应一种连接身份（如认证用户 vs 匿名用户），内部维护一份"消息监听器"注册
表（发布订阅模式），连接建立 / 心跳 / 重连全部封装在 Provider 里，组件不直接摸原生
WebSocket 对象：

```typescript
// 两种身份对应两个 Provider，共享同一套 Context API
<WebSocketProvider><App /></WebSocketProvider>
<AnonymousWebSocketProvider anonymousId={anonId} autoConnect={true}><PublicChat /></AnonymousWebSocketProvider>
```

组件通过 Hook 按频道订阅，Hook 内部向 Provider 注册一个监听器、按 `channel` 过滤消息：

```typescript
const { status, lastMessage, sendMessage, subscribe, unsubscribe } =
  useWebSocket<PayloadType>(channel, { autoSubscribe: true });
```

`autoSubscribe`（默认 true）让 Hook 挂载时自动订阅、卸载时自动取消——订阅引用计数（见
上文）在这一层生效，多个组件用同一个 Hook 订阅同一频道不会产生多余的网络订阅消息。

Provider 内部的监听器分发：

```typescript
const onMessage = useCallback((listener) => {
  listenersRef.current.add(listener);
  return () => listenersRef.current.delete(listener);  // 返回取消注册函数
}, []);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  listenersRef.current.forEach((listener) => listener(message));
};
```

---

## 乐观更新用客户端生成的临时 ID 关联服务端确认

发送前端立即生成一个临时 ID（如 UUID）并本地渲染乐观结果，随消息一起发给服务端；服务端
处理后原样把这个 ID 带回确认消息，前端拿它匹配并替换本地临时项——避免"先乐观出现一次、
服务端确认后又出现一次"导致的消息闪烁 / 重复。

```typescript
const clientMessageId = crypto.randomUUID();
setPendingUserMessage(userMessage);        // 立即显示
sendWsMessage(content, { clientMessageId });
// 服务端确认消息里带回同一个 clientMessageId，前端用它替换本地临时项而不是追加新项
```

---

## WebSocket 只负责"通知有变化"，数据仍走既有数据层重新拉取

不要把 WebSocket 推送的 `payload` 直接当权威数据源写入本地状态 / 缓存——WebSocket 是
fire-and-forget，可能丢消息，也不保证顺序。正确用法是收到事件后触发一次既有数据层（如
React Query）的缓存失效 / 重新拉取，真正的数据仍以 REST 拉取结果为准：

```typescript
useEffect(() => {
  if (!lastMessage) return;
  if (lastMessage.event === "queue_updated") {
    queryClient.invalidateQueries({ queryKey: ["queue"] });
  }
}, [lastMessage]);
```

这样即使某条 WebSocket 消息丢失、乱序或重复，最终状态仍会在下次成功拉取时收敛正确——
WebSocket 只是让"下次拉取"发生得更快，不承担数据一致性责任。

---

## 按传输特性选传输方式，不必所有实时场景都塞进 WebSocket

有些场景本质是"服务端单向流式吐字"（如 AI 生成逐字输出），这类场景用 SSE / HTTP 流式比
WebSocket 更简单：不需要维护双向连接状态，断线重试语义也简单，天然复用现有 HTTP 基础
设施（CDN、反向代理）。只有真正需要**双向**实时交互（如真人客服双向对话、协作编辑）的
场景才需要 WebSocket。

```typescript
if (mode === "interactive_realtime") {
  sendWsMessage(content);                   // 双向场景：WebSocket
} else {
  await sendStreamingSSE(content, onChunk);  // 单向流式生成：SSE
}
```

同一产品内两种传输方式并存是正常的，不必为了架构统一强行把单向流式场景也套进
WebSocket。

---
