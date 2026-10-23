# 登录

先看这次登录谁签发会话，再决定打不打开 `standard-api-security-baseline`。

## 自行托管：用该技能

项目自己签发会话，并且实现与脚手架一致时，读 `standard-api-security-baseline` 并按其做：

- `server/src/auth/domain/entities.py` 的 `AuthSession` 只存 token 的 SHA-256，原文不入库
- `server/src/auth/infrastructure/services/session_cookie_signer.py` 用 `secrets.token_urlsafe(32)` 生成原文，`itsdangerous.URLSafeTimedSerializer` 签名后写入 cookie
- `server/src/auth/presentation/_shared.py` 的 `_set_session_cookie` 带 `httponly`、`secure`、`samesite`
- 微信 / Apple 等第三方登录换到的是同一套 cookie 会话，不是把本地会话改成 JWT

认出这个人（手机号主身份、微信 / Apple 等渠道归并）读 `standard-multi-provider-auth`。本篇只决定会话谁签发。

## Vercel 或 Supabase：不用该技能

下面两种登录都不是这套会话。不要读 `standard-api-security-baseline`，也不要把它的条款移植过去：禁止 JWT、自建 cookie 签名、`SESSION_SECRET_KEY_HEX`、bcrypt 存密码、短信验证码多层防线、把第三方 identity token 收成自己的 cookie 会话。

**Supabase Auth** 签发的是 JWT 会话（`getSession` / `getUser` / `getClaims`）。授权走 RLS 和 `auth.uid()`，不走这份技能里的 cookie 中间件加 repository `where`。Supabase 自己的约束是：不用可被用户改的 `user_metadata` 做授权；删用户不会让已发出的 access token 立刻失效。这些以 Supabase 的 auth 技能为准。

**Vercel 一侧的登录** 是托管集成，不是自建 signer：Clerk、Better Auth、Descope、Auth0，以及 Sign in with Vercel（OIDC）。Vercel 的 auth 技能明确不要手写 Vercel OAuth 的 code 换 token。会话、密钥和吊销按所选集成的文档做。

登录方案还没定时先问，不要默认套脚手架的 cookie 会话。
