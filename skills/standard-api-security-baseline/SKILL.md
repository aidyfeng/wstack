---
name: standard-api-security-baseline
description: >
  安全基线：自托管不透明 HttpOnly cookie 会话下，改会话、越权过滤、后台 mTLS、CORS、密钥与
  bcrypt、CDN 真实 IP、验证码、第三方 identity token、富文本清洗或 PII 日志时使用。
---

# Web/API 安全基线

仅自行托管的不透明 HttpOnly cookie 会话（脚手架 `AuthSession` 只存 SHA-256，`SessionCookieSigner` 签名）使用本技能。Vercel（Clerk、Better Auth、Auth0、Descope、Sign in with Vercel）与 Supabase Auth：停，改走 `skills/wayne-mode/playbooks/login.md`；不要移植 cookie 签名、bcrypt，或「禁止 JWT」。

## 会话认证

token 用 `secrets.token_urlsafe(32)` 生成的不透明随机串，不含可解码载荷。签名后写入 cookie；数据库只存 `SHA-256(token)`，不存明文、不存签名值。存明文或签名值时，数据库泄露等于拿到全部会话。签名只防伪造。

解签失败或过期返回 `None`，上层视为未登录。

```python
def unsign(self, cookie_value: str, max_age_seconds: int) -> str | None:
    try:
        return _serializer().loads(cookie_value, max_age=max_age_seconds)
    except (SignatureExpired, BadSignature, Exception):
        return None      # 收敛成"未登录"，调用方只判一次
```

写 cookie 同时带 `httponly=True`（JS 读不到，XSS 偷不走）、`secure`（仅 HTTPS）、`samesite`（防 CSRF）。

用户端与运营后台各用独立的 secret、salt、cookie 名。signer 和校验函数只服务一端。共用 secret 时，一端的会话能在另一端使用，后台权限会泄漏到用户端。

新客户端沿用这套 cookie。另开 `Authorization: Bearer` 或自建 JWT 校验会多出一条要单独维护的认证路径。

| | HttpOnly cookie + 不透明 token | JWT / Bearer token |
|---|---|---|
| XSS | 前端读不到，偷不走 | 存 localStorage 就能被读走；存内存则每次刷新都要重登 |
| 吊销 | 删数据库一行，立即失效 | 到期前一直有效；黑名单等于回到有状态会话 |
| 载荷 | 随机串，不含信息 | payload 是 base64，任何人都能解开 |
| 代价 | 每次请求查一次 DB/缓存 | 无状态，省一次查询 |

吊销要即时生效；为 JWT 加黑名单就放弃了无状态，有缓存时少查一次库不是改用 JWT 的理由。校验外部平台签发的 identity token 仍用 JWT，见「第三方身份验证」，那不是自己签发会话。

## 越权防护

用户态数据的过滤写在 repository 的每条查询里。

```python
@dataclass
class OwnerScope:
    user_id: str | None

def _apply_owner(stmt, scope: OwnerScope):
    return stmt.where(Model.user_id == scope.user_id)
```

查询、更新、软删除都挂上 owner 过滤。每个新方法显式写这一行，没有全局默认兜底。在 UseCase 里查完再按 `user_id` 过滤时，SQL 层等于开了拉全表的窗口，漏一处就是全量泄露。

强制登录读中间件已写入的状态，不查库：

```python
def require_user_id(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise NotAuthenticatedException()     # 直接 401，不做匿名降级
    return user_id
```

中间件校验 cookie 后把 `user_id` 注入 `request.state`。没有 `user_id` 就 401。把未登录降级成匿名用户会让本应 401 的请求走进业务逻辑。

## 运营后台

后台子域会进证书透明度日志，地址是公开的。防护是两层：反向代理 mTLS（客户端出示自签 CA 签发的证书，握手失败连错误页都看不到），通过后再走后台会话登录。

```
admin.example.com {
    tls {
        client_auth {
            mode require_and_verify
            trust_pool file /etc/caddy/certs/admin-client-ca.pem
        }
    }
}
```

`client_auth` 挂在站点块顶层，SPA 静态资源与同源接口一起锁。页面公开、接口受限会把接口结构暴露给扫描器。

CA 公钥可以进 git。CA 私钥和客户端证书只留在本机，不进仓库。本地联调前先导入客户端证书，否则 TLS 握手失败，看不到应用层错误——这是缺证书，不是服务挂了。

ACME HTTP-01 走 80 端口明文，不经 TLS 握手，签发和续期不受 mTLS 影响。

## CORS

```python
if settings.app_env == AppEnv.production:
    kwargs = {"allow_origins": settings.cors_origins}      # 生产读白名单
else:
    kwargs = {"allow_origin_regex": ".*"}                  # 非生产动态回显
app.add_middleware(CORSMiddleware, **kwargs, allow_credentials=True, ...)
```

非生产用 `allow_origin_regex` 回显请求 origin。本地 Vite、预发 CDN、并行工作区的端口逐一写白名单容易漏，非生产不接真实用户数据。`allow_credentials=True` 时规范禁止 `allow_origins=["*"]`，字面量 `"*"` 不能代替这条 regex。

生产启动检查拒绝白名单里的 `localhost`、`127.0.0.1`、`"*"`，避免生产沿用非生产配置直到上线才发现。

`allow_credentials=True` 保留。前端跨域请求带 `credentials: 'include'`。CORS 已通但登录态丢失时，先查这个前端参数。

## 密钥与密码哈希

示例文件只放占位符。生产从 KMS / Vault 注入。启动检查拒绝生产环境仍是占位符，否则签名形同虚设，服务仍会照常启动。

```
SESSION_SECRET_KEY_HEX=REPLACE_WITH_RANDOM_HEX_64_CHARS
```

密码哈希用 bcrypt。`verify` 失败返回 `False`，不抛异常。

```python
def verify(self, plaintext: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return self._ctx.verify(plaintext, password_hash)
    except Exception:
        return False      # 哈希格式非法/算法不识别 → 视为不匹配
```

验证失败和哈希损坏都是 `False`。抛异常再漏 catch 会变成 500，攻击者能区分「密码错」和「哈希坏了」。

## 真实 IP

站在 CDN 后面时，连接层看到的是 CDN 节点 IP，拿它限流会全站连坐。只有请求带约定密钥头且值与配置一致时，才信任 CDN 传来的真实 IP：

```python
def client_ip(request: Request) -> str:
    secret = get_settings().cdn_origin_secret
    if secret and request.headers.get("X-From-CDN") == secret:
        if real_ip := request.headers.get("CDN-Real-IP", ""):
            return real_ip
    return get_remote_address(request)      # 否则回落连接层地址
```

密钥只配在 CDN 的回源请求头里，直连源站的请求拿不到它。密钥未配置时不信任该头。直接信任 `X-Forwarded-For` 或其它客户端可控头时，攻击者每个请求换一个假 IP，限流失效，日志里每条 IP 都不同，看起来像正常流量。

auth 与防爆破端点的限流 key 按 `standard-redis-patterns` 取纯 IP。

## 一次性验证码

敏感的一次性验证照这六层一起做：

| # | 防线 | 挡什么 |
|---|---|---|
| 1 | `secrets.randbelow` 生成，不用 `random` | 可预测种子 |
| 2 | 短 TTL（5 分钟） | 缩小枚举窗口 |
| 3 | 同标识 cooldown（60s，`SET NX EX`） | 压低枚举速率、防刷短信费 |
| 4 | 发送端点前置 PoW 验证码 | 机器人批量刷 |
| 5 | 发送端点 IP 限流 | 单机高频 |
| 6 | 滚动窗口用量告警 | 大规模异常 |

告警计数用滚动窗口（ZSET）。固定时间桶会把 23:59–00:01 的尖峰拆成两半，各自不过阈值。告警本身要有冷却（如 10 分钟），否则每条超限请求各告警一次，告警风暴把真问题淹没。

## 第三方身份验证

系统里用 JWT 的地方是校验外部平台签发的凭据。本地会话仍是上面的 cookie。

OAuth（如微信）：客户端只拿一次性 `code`，后端 server-to-server 换 token。appid/secret 只在服务端。

JWT（如 Apple）：验签之外校验 `audience`、`issuer`、`exp`。

```python
payload = jwt.decode(
    identity_token,
    signing_key.key,                  # 公钥从平台 JWKS 端点拉取，带缓存，不是自建密钥
    algorithms=["RS256"],
    audience=self._bundle_id,         # ← 漏了它：任何 App 签给自己 bundle_id 的 token 都能通过
    issuer=self._issuer,              # ← 漏了它：任何签发方都能冒充
)
```

只验签名时，平台签名有效的 token 可能是签给别的 App 的。验签通过不等于这张凭据是给你的。

## 富文本清洗

用户 HTML 要落库或回显时过两遍。

第一遍用 `nh3` / `bleach` 做标签和属性白名单。这类库通常只有 `url_schemes`（拦 `javascript:` / `data:`），没有域名过滤。第三方域名的 `<img src>` 会通过，成为访问者 IP 和 UA 的追踪信标。

第二遍用 HTML 解析器做域名白名单。host 不在白名单里就丢掉整个标签，不要只剥 `src`——空标签会让排版错乱。

```python
def sanitize_html(html: str) -> str:
    cleaned = nh3.clean(html, **_NH3_KWARGS)
    f = _ImgDomainFilter(_allowed_hosts())
    f.feed(cleaned); f.close()
    return f.result()
```

用正则代替解析器时，属性顺序、引号、大小写、换行都能绕过。`sanitize(sanitize(x)) == sanitize(x)`。只在反序列化或入口调用一次；别处再调用就是另一条会漏的路径。

## PII 日志

个人标识写入日志前走同一个公共函数。各处内联同一表达式会让格式漂移（有的留后 2 位、有的不留），同一个人的日志对不上，新模块也会漏抄。

```python
def mask_phone(phone: str) -> str:
    return phone[:3] + "****" + phone[-2:] if len(phone) >= 5 else phone
```

短字符串上 `phone[:3]` 与 `phone[-2:]` 会重叠，`"138"` 会输出 `138****38`。

测试夹具用固定测试值，只保留触发分支的结构，不用真实或打码后的片段。
