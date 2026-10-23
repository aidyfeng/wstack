---
name: standard-websocket-realtime
description: >
  WebSocket 实时通信。做服务端主动推送、在 WebSocket 与 SSE 之间选型，或排查多副本下部分连接收不到消息时使用。
---

# WebSocket 实时通信

适用：服务端要主动推送，REST 轮询的延迟不够。单进程用内存里的连接集合发送即可。「多进程广播」在多进程或多副本时才需要。

## 单连接与频道名

每个客户端一条 WebSocket。不同业务用频道订阅区分。认证、心跳、重连只挂在这一条连接上。

```
ws(s)://{host}/ws?token={jwt_token}       # 认证用户
ws(s)://{host}/ws?anonymous_id={anon_id}  # 匿名用户
```

频道名只用两种形态：`{prefix}` 或 `{prefix}:{id}`。前端、服务端、广播层用同一套名字。

| 频道类型 | 格式 | 示例 |
|---|---|---|
| 全局静态频道（无 ID） | `{prefix}` | `tasks` |
| 按分组 ID | `{prefix}:{id}` | `tenant:01ARZ3NDEK...` |
| 按资源 ID | `{prefix}:{id}` | `conversation:01ARZ3NDEK...` |

## 消息信封

客户端 → 服务端用固定的 `type`：

```json
{"type": "subscribe", "channel": "conversation:xxx"}
{"type": "unsubscribe", "channel": "conversation:xxx"}
{"type": "ping"}
{"type": "message", "channel": "conversation:xxx", "content": "Hello", "client_message_id": "uuid"}
```

服务端 → 客户端用固定四字段。`payload` 可以随 `event` 变，外层不变：

```json
{
  "channel": "conversation:xxx",
  "event": "message",
  "payload": {"id": "msg_123", "role": "human", "content": "..."},
  "timestamp": "2025-01-29T10:30:00Z"
}
```

订阅确认、心跳应答、错误走独立的 `type`，不塞进业务信封：

```json
{"type": "subscribed", "channel": "conversation:xxx"}
{"type": "unsubscribed", "channel": "conversation:xxx"}
{"type": "pong"}
{"type": "error", "message": "..."}
```

前端按这一套信封解析。没有固定外层时，每加一种 `event` 就要另写一套解析，未知 `event` 会漏掉而且不报错。

## 心跳与关闭码

客户端和服务端都做应用层心跳。服务端周期清扫空闲连接。反向代理和 NAT 会按自己的策略拆掉连接，TCP keepalive 替代不了这层。

- 客户端发 `{"type": "ping"}`，服务端回 `{"type": "pong"}`。
- 每收到任意消息都更新该连接的最后活跃时间，不限于 ping。
- 服务端扫掉超过阈值仍未活跃的连接，`close` 时带上专属关闭码。
- 认证用户和匿名用户可以配不同的超时。匿名连接的资源占用更保守。

心跳间隔和空闲超时的秒数按目标网络实测后再定。

自定义关闭码用 4000–4999。1000–2999 是协议保留段。客户端凭关闭码区分空闲超时、Token 无效、缺少认证参数。

| 码（占位，按新项目分配） | 含义 |
|---|---|
| 4000 | 空闲超时 |
| 4001 | Token 无效 |
| 4003 | 缺少认证参数 |

## 断线重连

简单场景用固定延迟重连，不把指数退避当默认。只在用户仍持有有效凭证时重连。正常关闭也可能是网络切换（移动网络切到 WiFi），不是用户退出。

```typescript
ws.onclose = () => {
  reconnectTimer = setTimeout(() => connect(), 5000);  // 固定延迟，占位值
};
```

连接断开后，服务端丢掉这条连接上的订阅。重连成功后，把当前所有活跃频道的订阅再发一遍。连上不等于原来的订阅还在。

## 订阅引用计数

同一页面里可以有多个组件订阅同一个频道。各自发订阅和取消订阅时，组件 B 卸载会把组件 A 还在用的频道退订掉。

频道级引用计数：0→1 才发订阅，1→0 才发取消订阅。中间只改本地计数。

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

## 多进程广播

单进程维护 `Set<Connection>` 再逐个发送，在只有一个进程时是对的。水平扩展之后，同一个频道的订阅者分散在不同进程里。A 进程收到的消息只能发给 A 自己的连接，B、C 上的订阅者收不到。单副本开发环境复现不了。现象是部分用户收不到推送，而且不报错。

多进程时，广播走所有进程都能访问的外部消息总线（常见是 Redis Pub/Sub）。每个进程既发布也订阅：

```
进程 A（持有连接 X）──publish──→ 消息总线 ──subscribe──→ 进程 B（持有连接 Y）
                                                     → 进程 C（持有连接 Z）
```

外部频道名在业务频道前加前缀：

```python
external_channel = f"ws:channel:{channel}"  # 例: ws:channel:conversation:01ARZ3NDEK...
```

发布时本地和总线可以分开关。默认两路都发。只通知本进程里的连接时关掉总线：

```python
await manager.publish_to_channel(
    channel="conversation:xxx",
    event="message",
    payload={...},
    via_bus=True,  # 默认同时经总线广播；仅需本地分发时传 False
)
```

## 发布者去重与进程级单例

每个进程启动时生成一个进程级 id，发到总线上的消息带上它。订阅回调里，发布者 id 是自己就跳过。

本进程通常先在本地分发一次，再发到总线。本进程也订阅着这条频道，会再收到自己刚发的消息。不去重，本进程的连接会收到两次。

```python
self._publisher_id = uuid.uuid4().hex  # 进程启动时生成一次

# 发布时附带
message = {"event": "...", "payload": {...}, "publisher_id": self._publisher_id}

# 订阅回调里跳过自己发布的
if data.get("publisher_id") == self._publisher_id:
    continue
```

管连接和订阅的 manager 用模块级单例，懒初始化。总线客户端在 manager 内部按需拿。import 时通常还没有事件循环，那时建连会绑错 loop。

```python
_manager: ConnectionManager | None = None

def get_connection_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager(bus_client=None)  # 总线客户端延迟获取
    return _manager
```

`reset_connection_manager()` 只在测试里调用。生产路径不重建这个单例。

## 频道内再过滤

全局频道上的某一条消息可能只该给其中一部分订阅者。例如 `tasks` 所有人都订了，但每条通知只推给 `payload` 里点名的用户。按字段过滤。不为每个用户单独开频道，否则频道数会跟着用户数涨。

```python
if channel == "tasks" and isinstance(payload.get("user_id"), str):
    recipients = identity_connections.get(payload["user_id"], set())
else:
    recipients = channel_subscribers.get(channel, set())
```

## 前端分层

一种连接身份一个 Provider（认证用户、匿名用户）。连接、心跳、重连放在 Provider 里。组件不拿原生 WebSocket。Provider 内部用一份监听器表做分发。

```typescript
// 两种身份对应两个 Provider，共享同一套 Context API
<WebSocketProvider><App /></WebSocketProvider>
<AnonymousWebSocketProvider anonymousId={anonId} autoConnect={true}><PublicChat /></AnonymousWebSocketProvider>
```

组件用 Hook 按频道订阅。Hook 向 Provider 注册监听器，并按 `channel` 过滤：

```typescript
const { status, lastMessage, sendMessage, subscribe, unsubscribe } =
  useWebSocket<PayloadType>(channel, { autoSubscribe: true });
```

`autoSubscribe` 默认 true：挂载时订阅，卸载时取消。引用计数在这一层，多个组件用同一个 Hook 订同一频道，只产生一次网络订阅。

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

## 乐观更新

发送时前端先生成临时 ID（如 UUID），立刻渲染，并随消息发给服务端。服务端原样带回这个 ID。前端用它替换本地临时项，而不是再追加一条。否则会先出现一次，确认后再出现一次。

```typescript
const clientMessageId = crypto.randomUUID();
setPendingUserMessage(userMessage);        // 立即显示
sendWsMessage(content, { clientMessageId });
// 服务端确认消息里带回同一个 clientMessageId，前端用它替换本地临时项而不是追加新项
```

## 推送之后重新拉取

WebSocket 只表示「有变化」。收到事件后，让既有数据层重新拉取，例如让 React Query 失效对应 query。`payload` 不写入本地状态或缓存当权威数据。推送可能丢、乱序、重复。下次拉取成功时状态会收敛；推送只是让这次拉取更早发生。

```typescript
useEffect(() => {
  if (!lastMessage) return;
  if (lastMessage.event === "queue_updated") {
    queryClient.invalidateQueries({ queryKey: ["queue"] });
  }
}, [lastMessage]);
```

## WebSocket 与 SSE

双向实时（真人客服、协作编辑）用 WebSocket。服务端单向往外吐字（例如生成过程逐字输出）用 SSE 或 HTTP 流：不用维护双向连接状态，断线重试更简单，也走现有的 HTTP 设施（CDN、反向代理）。同一产品里两种传输可以并存。

```typescript
if (mode === "interactive_realtime") {
  sendWsMessage(content);                   // 双向场景：WebSocket
} else {
  await sendStreamingSSE(content, onChunk);  // 单向流式生成：SSE
}
```
