---
name: standard-redis-patterns
description: >
  Redis 使用规范——连接生命周期、缓存 key 版本化、跨进程失效（pub/sub）、故障降级、限流 key
  选取、幂等 SET NX EX、测试隔离。加缓存、改缓存结构、做限流、做防重放/冷却、写跨进程失效时使用。
  几条易踩的：缓存值结构变了要 bump key 里的版本号而不是原地改值（否则灰度期新旧代码互相读到
  对方的格式）；限流 key 认 cookie 的话攻击者清 cookie 就能绕过，auth 端点必须用纯 IP；
  幂等要用原子 SET NX EX，先 GET 再 SET 之间有竞态窗口。
  一条要分清的：**静默降级**是有意设计（Redis 挂了回源 DB，业务不中断），**静默失败**是缺陷
  （数据悄悄错了没人知道）——两者都"不报错"，处理方式相反。
  预设 Redis 作加速层而非数据源。
---

# Redis 使用规范

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

- Redis 是**加速层**，不是数据来源——任何缓存都能回源，任何 Redis 故障都不该让请求失败
- 异步客户端（`redis.asyncio`），应用有 lifespan 管理连接

**先分清两个都"不报错"的概念，它们处理方式相反：**

| | 静默降级 | 静默失败 |
|---|---|---|
| 性质 | **有意设计** | **缺陷** |
| 例子 | Redis 超时 → 回源 DB，请求照常完成 | 缓存结构变了没 bump 版本号 → 读到旧格式解析出错误结果 |
| 特征 | 有 warning 日志、有回源路径、行为可预期 | 无日志、无信号，只是结果悄悄错了 |
| 该做的 | 保持（见「故障降级」节） | 消除（本篇其余各节） |

---

## 连接：单例 + 有界关闭

**全项目只用一个 `get_redis()` 单例**，禁止各处自建 `Redis()` / `ConnectionPool()`——散落的
连接池谁也管不了生命周期，关闭时必然漏掉。

关闭时先 `aclose()` client 再 `aclose()` pool，每步单独 try/except，失败只 warning，不阻断
关闭流程。

**关闭必须有界等待，且注意 `asyncio.wait` 与 `wait_for` 的区别**——完整论证见
`standard-fastapi-ddd-backend` 的「lifespan 关闭步骤必须有超时上界」。这里只记 Redis 场景
特有的两点：

**① pub/sub 连接是最容易半开的那个。** 订阅连接长期零流量，NAT 表项被回收后连接半开，
`finally` 块里的 `unsubscribe` 网络往返**永久挂起**。等待这类 task 必须用
`asyncio.wait(timeout=)`——`wait_for` 会一起挂住。

**② 独立叶子清理反而适合 `wait_for`。** 不涉及"`finally` 里挂起网络调用"的单次操作（如
`pubsub.aclose()` 本身），用 `wait_for` + `contextlib.suppress` 包一层硬超时更合适，因为它能
真正取消掉：

```python
with contextlib.suppress(Exception):
    await asyncio.wait_for(pubsub.aclose(), timeout=shutdown_step_timeout)
```

---

## 缓存 key 版本化

Key 格式 `{模块}:{范围}:v{N}`：

```
states:all:v14
voice:all:v2
sections:v1:{state_key}
```

**缓存值的结构或语义变了，bump 版本号，不要原地改值。** 旧 key 因版本号变化自然成为死 key，
靠 TTL 过期。

原地改值的后果发生在**灰度期**：跑旧代码的实例（未重启的进程）读到新格式会解析崩溃，或反过来
新代码读到旧格式脏数据——两个方向都会出错，且只在部署窗口内出现，事后难复现。

何时 bump：

- 缓存值的字段、类型、嵌套结构变化
- 缓存值的**语义**变化，即使结构没变——形状一样但含义变了，消费方按旧假设解析出的是错误结果，
  这种最难查
- **不需要 bump**：纯 bug fix、不改变值形状与含义的性能优化

附带好处：升版即部署即读新数据，不依赖运维手工执行 `redis del` 这类容易漏掉的步骤。

---

## 跨进程失效：pub/sub + 两道兜底

写路径与读缓存分属不同进程时（如管理后台写、面向用户的服务读），失效走 Redis pub/sub 解耦。
**写侧不要反向 import 读侧的缓存实现**——那会把两个独立部署的服务在代码层绑死。

```python
# 写侧：改完 DB 后发布失效消息，fire-and-forget，失败只 warn
await publish_invalidation(reason="content_publish")

# 读侧：进程常驻订阅，收到消息失效自己的缓存
```

**pub/sub 是 fire-and-forget，订阅者不在线时消息直接丢失、不重投。** 所以必须有两道兜底：

1. **订阅端启动时无条件失效一次** —— 补偿宕机窗口内错过的消息
2. **缓存仍设 TTL** —— 覆盖连接断线、消费者进程死掉等极端情况

**不做重连重试**：订阅循环内单条消息处理失败或连接中断，不必自动重连——TTL 已覆盖这个场景，
进程重启（下次部署）自然恢复订阅。加重连逻辑是在给一个已经有兜底的路径增加复杂度。

---

## 故障降级：Redis 是加速路径

所有 Redis 读写 try/except 包裹，失败只 `logger.warning`，**绝不抛出阻断主流程**：

```python
async def get(self, key: str) -> Result | None:
    try:
        raw = await get_redis().get(_key(key))
    except Exception as e:
        logger.warning("cache_get_failed", key=key, error=str(e))
        return None          # 调用方自然回源 DB
    ...
```

- 一个缓存类的 `get` / `set` / `invalidate` **每个方法都要包**，不能只包读不包写
- **反序列化失败**（脏数据、版本不兼容）按同样方式处理：`return None`，不让异常上冒
- 启动期 `ping` 探测失败也不阻断服务启动

这是上面表格里的「静默降级」——它有日志、有回源路径，是设计而非缺陷。

**缓存层级**：缓存实现在 repository / service 层。不要在 router 层加 HTTP 响应缓存装饰器——
响应级缓存会把鉴权、个性化、trace_id 一起缓存进去，失效边界也说不清。

---

## 限流 key 选取

**一般读接口用 `scope_key`**：`user_id` > `anonymous_id` > IP 逐级回退。

```python
def scope_key(request: Request) -> str:
    if user_id := getattr(request.state, "user_id", None):
        return f"user:{user_id}"
    if anon := getattr(request.state, "anonymous_id", None):
        return f"anon:{anon}"
    return f"ip:{client_ip(request)}"
```

理由：纯 IP 限流会在共享出口（公司、校园、WiFi）下误伤同网段的不同用户。

**auth / 防爆破端点必须显式传纯 IP 的 key**：

```python
@limiter.limit("5/minute", key_func=ip_key)
async def login(...): ...
```

理由：`scope_key` 认 `anonymous_id` cookie，攻击者清 cookie 就能拿到新 anon id 绕过限流。
防爆破场景必须用不可绕过的维度。

**真实 IP 的信任门。** 站在 CDN / 反向代理后面时，只在请求同时携带一个**共享密钥头**且值匹配
时，才信任 `X-Real-IP` 之类的头；密钥未配置时永不信任，直接退回连接层地址。

否则攻击者绕过 CDN 直连源站、自己伪造该头，就能无限轮换限流 key——**限流形同虚设，且看不出
异常**（日志里每个请求的 IP 都不一样，像是正常流量）。

---

## 幂等：SET NX EX

幂等 / 防重放 / 防重复触发一律用原子 `SET key val NX EX <ttl>`：

```python
# ✅ 一条原子命令：不存在才设，同时给 TTL
ok = await redis.set(cooldown_key, "1", nx=True, ex=60)
if not ok:
    raise CooldownException()

# ❌ 先 GET 判断再 SET —— 两步之间有竞态窗口，并发请求会全部通过
if not await redis.get(cooldown_key):
    await redis.set(cooldown_key, "1", ex=60)
```

典型场景：验证码发送冷却、告警去重（避免同一阈值反复告警）、PoW / challenge 防重放。

**边界**：`SET NX EX` 只解决"同一个 key 的一次性占用"，**不是通用互斥锁**。需要跨请求持锁
保护一段临界区（读-改-写）时，它挡不住——那需要 Redlock 之类的方案，引入前先评估是否真的
需要分布式锁，多数场景可以用数据库的唯一约束或乐观锁替代。

---

## 测试隔离

新增 Redis 读写 / 发布 / 订阅逻辑，**必须在入口判断测试标记并短路**：

```python
def _cache_enabled() -> bool:
    return os.environ.get("TEST_DB_FLAG") != "1"

async def publish_invalidation(reason: str) -> None:
    if not _cache_enabled():
        return
    ...
```

理由：多个 worktree / 开发者常共享同一个远端 Redis。测试若不短路，会互相污染缓存与频道状态——
表现为"某个测试单独跑过、一起跑就挂"这类最难查的问题。

**限流 storage 同理**：测试环境强制退化成内存 storage，不连 Redis。

短路要写在**最外层入口**（publish / subscribe / 缓存类的每个公共方法），不要指望调用方记得判断。

---
