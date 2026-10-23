# Redis

加缓存、改缓存结构、做限流、做防重放或冷却、写跨进程失效时，读 `standard-redis-patterns`。

Redis 只做加速层。缓存都能回源，Redis 故障不让请求失败。业务数据的表结构见 [persistence](persistence.md)。

测试要避开共享 Redis 时，同样按这篇里的测试隔离做，不另写一套连接。
