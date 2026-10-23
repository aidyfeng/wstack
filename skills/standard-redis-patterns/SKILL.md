---
name: standard-redis-patterns
description: >
  Redis 加速层。加缓存、改缓存结构、做限流、做防重放或冷却、写跨进程失效，或让测试避开共享 Redis 时使用。
---

# Redis 加速层

Redis 只做加速层：任何缓存都能回源，Redis 故障不让请求失败。客户端用 `redis.asyncio`，连接由应用的 lifespan 管理。

## 连接

全项目一个 `get_redis()` 单例。别处再 `Redis()` / `ConnectionPool()`，关闭时会漏掉。

关闭时先 `aclose()` client，再 `aclose()` pool。每步单独 try/except，失败只 warning，不阻断关闭。

关闭要有超时上界。总则见 `standard-fastapi-ddd-backend`（等待任务用 `asyncio.wait`）。Redis 这里另外两点：

pub/sub 连接最容易半开。订阅长期零流量，NAT 表项被回收后连接半开，`finally` 里的 `unsubscribe` 会永久挂起。等这类 task 用 `asyncio.wait(timeout=)`。`wait_for` 会一起挂住。

不涉及「`finally` 里挂起网络调用」的单次叶子清理，用 `wait_for` 加 `contextlib.suppress`，它能真正取消：

```python
with contextlib.suppress(Exception):
    await asyncio.wait_for(pubsub.aclose(), timeout=shutdown_step_timeout)
```

## 缓存 key 版本

Key 格式 `{模块}:{范围}:v{N}`：

```
states:all:v14
voice:all:v2
sections:v1:{state_key}
```

缓存值的结构或语义变了，bump 版本号，不在原地改值。旧 key 因版本号变化成为死 key，靠 TTL 过期。升版后部署即读新数据，不靠手工 `redis del`。

原地改值会撞上灰度期：跑旧代码的实例读到新格式会解析崩溃，新代码读到旧格式则是脏数据。两个方向都会错，而且只在部署窗口里出现，事后难复现。

何时 bump：

- 缓存值的字段、类型、嵌套结构变了
- 语义变了，即使结构没变。形状一样但含义变了，消费方按旧假设解析出的是错误结果，这种最难查
- 纯 bug fix、不改变值形状与含义的性能优化，不 bump

## 跨进程失效

写路径和读缓存不在同一个进程时（管理后台写、面向用户的服务读），失效走 Redis pub/sub。写侧不反向 import 读侧的缓存实现，避免两个独立部署的服务在代码层绑死。

```python
# 写侧：改完 DB 后发布失效消息，fire-and-forget，失败只 warn
await publish_invalidation(reason="content_publish")

# 读侧：进程常驻订阅，收到消息失效自己的缓存
```

pub/sub 是 fire-and-forget。订阅者不在线时消息直接丢，不重投。两道兜底都要有：

1. 订阅端启动时无条件失效一次，补上宕机窗口里错过的消息。
2. 缓存仍设 TTL，盖住断线和消费者进程挂掉。

订阅循环里单条消息失败或连接中断，不自动重连。TTL 已经盖住；进程重启（下次部署）会恢复订阅。重连是在已有兜底的路径上加复杂度。

## 故障降级

Redis 读写用 try/except 包住。失败只 `logger.warning`，不抛出去阻断主流程。调用方拿到空结果就回源。

```python
async def get(self, key: str) -> Result | None:
    try:
        raw = await get_redis().get(_key(key))
    except Exception as e:
        logger.warning("cache_get_failed", key=key, error=str(e))
        return None          # 调用方自然回源 DB
    ...
```

一个缓存类的 `get`、`set`、`invalidate` 每个方法都包，不能只包读不包写。反序列化失败（脏数据、版本不兼容）同样 `return None`，异常不上冒。启动期 `ping` 失败只 warning，不阻断启动。启动探针的总则见 `standard-fastapi-ddd-backend`。

这是有意降级：有 warning，有回源，请求继续。

缓存做在 repository / service 层。路由上不加 HTTP 响应缓存装饰器。响应级缓存会把鉴权、个性化和 trace_id 一起缓存进去，失效边界也说不清。

## 限流 key

一般读接口用 `scope_key`，逐级回退：`user_id` > `anonymous_id` > IP。

```python
def scope_key(request: Request) -> str:
    if user_id := getattr(request.state, "user_id", None):
        return f"user:{user_id}"
    if anon := getattr(request.state, "anonymous_id", None):
        return f"anon:{anon}"
    return f"ip:{client_ip(request)}"
```

纯 IP 会在共享出口（公司、校园、WiFi）下误伤同网段的不同用户。

auth 和防爆破端点显式传纯 IP 的 key：

```python
@limiter.limit("5/minute", key_func=ip_key)
async def login(...): ...
```

`scope_key` 认 `anonymous_id` cookie。攻击者清 cookie 就换一个 anon id，限流被绕过。防爆破用清不掉的维度。

限流用的 IP 只在 `X-From-CDN` 与配置的回源密钥一致时采用 `CDN-Real-IP`，否则用连接层地址。不信任 `X-Forwarded-For` 这类客户端能改的头。取 IP 的函数是 `client_ip()`，实现写在 `standard-api-security-baseline`。登录不是自托管 cookie 时，只借用这个取 IP 方式。

## 幂等：SET NX EX

幂等、防重放、防重复触发用原子 `SET key val NX EX <ttl>`：

```python
# ✅ 一条原子命令：不存在才设，同时给 TTL
ok = await redis.set(cooldown_key, "1", nx=True, ex=60)
if not ok:
    raise CooldownException()

# ❌ 先 GET 判断再 SET —— 两步之间有竞态窗口，并发请求会全部通过
if not await redis.get(cooldown_key):
    await redis.set(cooldown_key, "1", ex=60)
```

典型场景：验证码发送冷却、告警去重（同一阈值不反复告警）、PoW / challenge 防重放。

`SET NX EX` 只解决同一个 key 的一次性占用，不是跨请求的互斥锁。读-改-写的临界区用数据库唯一约束或乐观锁。真要分布式锁再评估 Redlock。

## 测试隔离

新增 Redis 读写、发布、订阅，在入口看测试标记并短路：

```python
def _cache_enabled() -> bool:
    return os.environ.get("TEST_DB_FLAG") != "1"

async def publish_invalidation(reason: str) -> None:
    if not _cache_enabled():
        return
    ...
```

多个 worktree 和开发者常共享同一个远端 Redis。测试不短路会互相污染缓存和频道，表现为某个测试单独跑过、一起跑就挂。

限流 storage 在测试环境用内存，不连 Redis。

短路写在最外层入口：publish、subscribe、缓存类的每个公共方法。不靠调用方记得判断。
