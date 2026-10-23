---
name: standard-api-security-baseline
description: >
  Web/API 安全基线——会话认证（签名 cookie 而非 JWT）、越权防护、后台 mTLS、CORS、密钥与
  密码哈希、真实 IP 与限流 key、验证码防爆破、第三方身份验证、富文本清洗、PII 日志脱敏。
  仅当项目自行托管登录（不透明 HttpOnly cookie 会话，同脚手架 auth）时使用。
  Vercel 登录（Clerk、Better Auth、Auth0、Descope、Sign in with Vercel）和 Supabase Auth
  不适用；先看 wayne-mode 的 playbooks/login.md，不要把本篇套上去。
  这里的失败模式是**防线看起来在、实际不生效**：HTML 清洗库不拦图片域名（只拦协议）、
  第三方 token 只验签名不验 audience 会跨 App 被接受、限流信任客户端可伪造的 IP 头等于没限流、
  查询漏了 owner 过滤就是拉全表。它们都不报错，日志看着一切正常。
  预设 HttpOnly cookie 会话 + 应用层鉴权；不适用于纯 JWT 无状态架构。
---

# Web/API 安全基线

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

- 项目自行托管登录。会话走 HttpOnly cookie，token 是不透明随机串，不是 JWT。脚手架的实现是 `AuthSession` 只存 SHA-256、`SessionCookieSigner` 签名后写入 cookie。
- Vercel 或 Supabase 签发登录时本篇不适用，停在这里，按 `wayne-mode` 的 `playbooks/login.md` 处理。
- 有独立的运营后台，与面向用户的服务分开部署
- 站在 CDN / 反向代理之后

本篇的失败模式与别处不同：**防线看起来在、实际不生效**。加了清洗库但它不管域名、验了签名但
没验受众、配了限流但 key 可以伪造——这些都不抛异常、不留日志，安全审计时甚至能看到"我们做了
防护"。所以每条都要问一句：**它到底挡住了什么，没挡住什么。**

---

## 会话认证：不透明 token，不是 JWT

- **token 本体是随机串**（`secrets.token_urlsafe(32)`），不含任何可解码信息
- **签名后写 cookie，DB 只存 `SHA-256(token)`**——不存明文、不存签名值。签名仅用于防伪造，
  哈希用于防"数据库泄露即等于拿到所有会话"
- **解签失败/过期一律返回 `None`**，上层视为未登录，不抛异常——认证失败是正常流程分支，不是
  异常情况

```python
def unsign(self, cookie_value: str, max_age_seconds: int) -> str | None:
    try:
        return _serializer().loads(cookie_value, max_age=max_age_seconds)
    except (SignatureExpired, BadSignature, Exception):
        return None      # 收敛成"未登录"，调用方只判一次
```

**写 cookie 三件套必须齐：** `httponly=True`（JS 读不到，XSS 偷不走）、`secure`（仅 HTTPS）、
`samesite`（防 CSRF）。少任何一个都会让前两条的努力白费。

**多端会话完全隔离。** 面向用户的服务与运营后台各用独立的 secret / salt / cookie 名，
**任何代码不得跨端复用 signer 或校验函数**。共用一个 secret 意味着一端的会话能在另一端使用——
后台权限就此泄漏到用户端。

新客户端接入时统一走既有 cookie 机制，不要为它单开一条 `Authorization: Bearer` 或自建 JWT
校验——多一条认证路径就多一处要同步维护的攻击面。

### 为什么不用 JWT / Bearer token

这个选择会被反复提议（它是很多项目的默认做法），取舍记在这里，免得每次重新论证：

| | HttpOnly cookie + 不透明 token（本方案） | JWT / Bearer token |
|---|---|---|
| XSS 下的后果 | 前端读不到，**偷不走** | 存 localStorage 就能被读走；存内存则每次刷新页面都要重登 |
| 吊销 | DB 里删一行，**立即失效** | 签发后到期前一直有效，要吊销就得再维护一张黑名单——那就等于回到了有状态会话 |
| 载荷泄露 | token 是随机串，不含任何信息 | payload 只是 base64，任何人都能解开看内容 |
| 代价 | 每次请求查一次 DB/缓存 | 无状态，省一次查询 |

**决定性的那条是吊销。** 无状态是 JWT 的卖点，但它同时意味着"签出去就收不回"——账号被盗、
权限变更、强制下线这些场景都要求即时失效。为此加黑名单等于放弃无状态，那还不如一开始就用
有状态会话。省下的那一次查询，在有缓存的前提下不构成理由。

**唯一的例外是验证外部平台签发的凭据**（如第三方登录的 identity token）——那是别人签的，
只能验签，见下方「第三方身份验证」。这与"自己签发会话"是两回事，不要混为一谈。

---

## 越权防护：过滤下沉到 SQL

用户态数据的过滤条件必须写在 **repository 的每条查询**里，不是在拿到数据之后：

```python
@dataclass
class OwnerScope:
    user_id: str | None

def _apply_owner(stmt, scope: OwnerScope):
    return stmt.where(Model.user_id == scope.user_id)
```

- ❌ 在 UseCase 层查完再按 `user_id` 过滤——SQL 层不过滤就等于给了拉全表的窗口，一旦某处忘了
  过滤就是全量泄露
- ✅ **查询 / 更新 / 软删除三类操作**都挂上 owner 过滤。没有全局默认兜底，每个新方法都要重复
  写这一行——这是刻意的：显式重复比"以为有默认过滤"安全

**强制登录的判断读中间件已校验的状态，不查库：**

```python
def require_user_id(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise NotAuthenticatedException()     # 直接 401，不做匿名降级
    return user_id
```

中间件校验 cookie 后把 `user_id` 注入 `request.state`，这个依赖只读不查库。**不要做"没登录就
当匿名用户"的降级**——那会让本应 401 的请求悄悄走进业务逻辑。

---

## 运营后台：infra + 应用双层门禁

后台子域**藏不住**（Let's Encrypt 签发的证书会进 CT 公开日志，域名是公开的），所以靠"没人知道
地址"不算防护。两层，缺一不可：

1. **infra 层 mTLS**：反向代理要求客户端出示自签 CA 签发的证书，握手不过连错误页都看不到
2. **应用层登录**：mTLS 通过后仍要走后台会话登录

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

**`client_auth` 挂在站点块顶层**，SPA 静态资源与同源接口一起锁死——不存在"页面公开、接口受限"
的中间态（那种中间态会把接口结构暴露给扫描器）。

**证书分发**：CA 公钥可以进 git；**CA 私钥与客户端证书只在本机**，不进仓库。本地联调后台前必须
先导入客户端证书，否则 TLS 握手直接失败，看不到任何应用层错误——这个现象要认得，否则会误以为
是服务挂了。

ACME HTTP-01 走 80 端口明文、不经 TLS 握手，证书签发续期不受 mTLS 影响。

---

## CORS：非生产放开是有意设计

```python
if settings.app_env == AppEnv.production:
    kwargs = {"allow_origins": settings.cors_origins}      # 生产读白名单
else:
    kwargs = {"allow_origin_regex": ".*"}                  # 非生产动态回显
app.add_middleware(CORSMiddleware, **kwargs, allow_credentials=True, ...)
```

**不要为了"加固"把非生产也改成白名单**——本地 Vite、预发 CDN 域名、多个并行工作区的端口，逐一
维护白名单成本高且容易漏，而非生产环境不接真实用户数据。

**为什么不能用字面量 `"*"`**：`allow_credentials=True` 时 CORS 规范禁止 `allow_origins=["*"]`，
只能用 regex 动态回显请求 origin。

**生产必须由启动检查兜底**：强制白名单不含 `localhost` / `127.0.0.1` / `"*"`，让"生产沿用了
非生产配置"这件事在启动时就炸，而不是上线后才发现。

**与 cookie 认证的配合**：`allow_credentials=True` 是必须项，且前端跨域请求要显式带
`credentials: 'include'`。排查"CORS 通了但登录态丢失"先查前端这个参数，不是后端配置问题。

---

## 密钥与密码哈希

**密钥全部走环境配置，示例文件只放占位符：**

```
SESSION_SECRET_KEY_HEX=REPLACE_WITH_RANDOM_HEX_64_CHARS
```

生产从 KMS / Vault 注入，**启动检查拦截"生产环境仍是占位符"**——否则一个忘记配置的密钥会让
签名形同虚设，而服务照常启动、毫无提示。

**密码哈希用 bcrypt，`verify` 失败不抛异常：**

```python
def verify(self, plaintext: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return self._ctx.verify(plaintext, password_hash)
    except Exception:
        return False      # 哈希格式非法/算法不识别 → 视为不匹配
```

统一收敛成 `bool`：验证失败 = 哈希损坏 = `False`。让它抛异常会在上层多出一条要单独 catch 的
错误路径，而漏 catch 的后果是 500——攻击者能据此区分"密码错"和"这个账号的哈希坏了"。

---

## 真实 IP：双重信任门

站在 CDN 后面时连接层只能看到 CDN 节点 IP，**直接拿它限流会全站连坐**（一个节点服务成千上万
用户）。但客户端可伪造的头也不能直接信。

只有**同时满足**「请求带约定的密钥头」且「值与配置一致」时，才信任 CDN 传来的真实 IP 头：

```python
def client_ip(request: Request) -> str:
    secret = get_settings().cdn_origin_secret
    if secret and request.headers.get("X-From-CDN") == secret:
        if real_ip := request.headers.get("CDN-Real-IP", ""):
            return real_ip
    return get_remote_address(request)      # 否则回落连接层地址
```

- 密钥只配在 CDN 控制台的「回源请求头」里，**绕过 CDN 直连源站的请求拿不到它**
- **密钥未配置时永不信任该头**——未接 CDN 的环境行为不变，也不会因为"忘了配"而敞开
- ❌ 直接信任 `X-Forwarded-For` / 任何客户端可控头：攻击者每个请求换一个假 IP，限流形同虚设，
  **而日志里每条请求 IP 都不同，看起来就像正常流量**

**auth 端点固定用纯 IP key，不用带 cookie 的复合 key。** 复合 key（user > anon > IP）适合内容
类读接口——识别每个客户端、不被共享出口 IP 误伤；但攻击者清 cookie 就能拿到新的匿名 id 绕过。
key 选取的完整规则见 `standard-redis-patterns`。

---

## 一次性验证码：多层独立防线

新增任何敏感一次性验证操作照抄这套组合，**单一防线都不够**：

| # | 防线 | 挡什么 |
|---|---|---|
| 1 | `secrets.randbelow` 生成，**禁用 `random`** | 可预测种子 |
| 2 | 短 TTL（5 分钟） | 缩小枚举窗口 |
| 3 | 同标识 cooldown（60s，`SET NX EX` 原子实现） | 压低枚举速率、防刷短信费 |
| 4 | 发送端点前置 PoW 验证码 | 机器人批量刷，不给免费重试预算 |
| 5 | 发送端点 IP 限流 | 单机高频 |
| 6 | 滚动窗口用量告警 | 大规模异常的兜底发现 |

两个细节：

- **告警计数用滚动窗口（ZSET），不是固定时间桶**——固定桶会让跨桶的 spike（23:59–00:01）被拆成
  两半、各自都不过阈值而漏检
- **告警本身要有冷却**（如 10 分钟），否则每条超限请求都单独告警一次，形成告警风暴，真问题反而
  被淹没

---

## 第三方身份验证

这类流程往往是**整个系统里唯一用到 JWT 的地方**——用于验证外部平台签发的凭据，不是签发自己的
会话。不要因此把本地会话也改成 JWT。

**OAuth 类（如微信）：客户端只拿一次性 `code`，后端 server-to-server 换 token。** appid/secret
只在服务端持有，从不下发客户端——客户端因此无法伪造身份。

**JWT 类（如 Apple）：验签之外必须校验 `audience` + `issuer` + `exp`，缺一不可。**

```python
payload = jwt.decode(
    identity_token,
    signing_key.key,                  # 公钥从平台 JWKS 端点拉取，带缓存，不是自建密钥
    algorithms=["RS256"],
    audience=self._bundle_id,         # ← 漏了它：任何 App 签给自己 bundle_id 的 token 都能通过
    issuer=self._issuer,              # ← 漏了它：任何签发方都能冒充
)
```

**只验签名不验 `audience` 是这类集成最常见的漏洞**：签名是平台签的、确实有效，但那张 token 本
来是发给**别的 App** 的。验签通过 ≠ 这张凭据是给你的。

---

## 富文本清洗：两遍，缺一不可

用户提交的 HTML 要落库/回显时：

**第一遍：标签与属性白名单**（`nh3` / `bleach` 之类）。

**但要知道它没管什么**：这类库通常只有 `url_schemes`（拦 `javascript:` / `data:` 协议），
**没有域名过滤**——第三方域名的 `<img src>` 会原样通过，成为访问者 IP 与 UA 的追踪信标。

**第二遍：用 HTML 解析器做域名白名单**，host 不在白名单里就**整个标签丢掉**（不是只剥 `src`——
留着空标签会让排版错乱且意图不明）：

```python
def sanitize_html(html: str) -> str:
    cleaned = nh3.clean(html, **_NH3_KWARGS)
    f = _ImgDomainFilter(_allowed_hosts())
    f.feed(cleaned); f.close()
    return f.result()
```

❌ 用正则代替 HTML 解析器——属性顺序、引号形态、大小写、换行都能绕过。

**两条约束：**

- **必须幂等**：`sanitize(sanitize(x)) == sanitize(x)`。否则任何"读出来再存回去"的流程都会
  逐次改写内容，破坏序列化的 round-trip 恒等
- **唯一收口点**：只在反序列化/入口处调用一次，**别处调用一律视为漏洞**。多个调用点意味着
  总有一条路径会漏

---

## PII 日志脱敏

含个人标识的字段写日志前必须脱敏：

```python
def mask_phone(phone: str) -> str:
    return phone[:3] + "****" + phone[-2:] if len(phone) >= 5 else phone
```

长度保护不是多余的——短字符串上 `phone[:3]` 与 `phone[-2:]` 会**重叠**，脏数据 `"138"` 会输出
`138****38`，把仅有的位数重复暴露一遍。

**脱敏必须收敛成一个公共函数。** 各处内联同一个表达式的结果是格式漂移（有的带后 2 位、有的
不带），日志检索时同一个人的记录对不上；更糟的是新模块直接漏抄。

测试夹具同样禁止真实号码，包括打码后的残缺片段。用固定测试值，只保留触发分支所需的结构。

---
