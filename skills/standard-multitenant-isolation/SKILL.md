---
name: standard-multitenant-isolation
description: >
  多租户数据隔离。给查询加上租户边界、传递当前租户上下文，或排查跨租户数据泄露时使用。
---

# 多租户数据隔离

一个账号同时属于多个租户（组织、工作空间、团队）时，数据范围按当前正在操作的租户切。会话由谁签发见 `skills/wayne-mode/playbooks/login.md`。单租户按属主过滤见 `standard-api-security-baseline` 的 `OwnerScope`。

## 每条查询都带租户过滤

入口校验只证明当前用户属于请求声明的租户，不证明请求体或路径里的其他资源 id 也属于这个租户。过滤写在查询上：

```python
# 入口验证了成员身份，查询本身没有租户过滤
async def get_task(tenant: TenantContext, task_id: str):
    task = await task_repo.get_by_id(task_id)   # 没有 filter(tenant_id=tenant.id)
    # task_id 换成另一个租户的 ID 也能查到
```

```python
# 过滤条件在查询上，tenant_id 是方法签名里的参数
async def get_by_id(self, task_id: str, tenant_id: str) -> Task | None:
    return await db.query(Task).filter_by(id=task_id, tenant_id=tenant_id).first()
```

查询、更新、软删除都这样写。每个方法自己带 `tenant_id`，不靠全局中间件默认补上。批量导出和统计最容易漏掉这层。

## 租户上下文怎么传递

| 方式 | 机制 | 客户端能否改这个值 | 适合 |
|---|---|---|---|
| 请求头声明 | 每次请求显式带「现在操作哪个租户」 | 能。必须再做成员校验 | 前端频繁切租户查数据，不想每次重新登录 |
| 会话内绑定 | 登录或切换租户时把租户 ID 写入服务端签发的会话，后续请求从会话读 | 不能。值在服务端签发的会话里 | 一次会话对应一个租户，切换要走专门动作 |
| 路径参数 | URL 带租户 ID，如 `/tenants/{tenant_id}/resources` | 能。和请求头一样要做成员校验 | 可加书签、可分享给同租户的其他成员 |

请求头和路径里的租户 ID 由客户端声明。先确认当前用户是该租户成员，再使用：

```python
async def get_tenant_context(
    tenant_id: str,                                   # 来自请求头或路径，客户端可控
    current_user: TokenPayload,
) -> TenantContext:
    membership = await membership_repo.get(tenant_id, current_user.user_id)
    if membership is None:
        raise TenantAccessDeniedException()           # 不是成员，直接拒绝
    return TenantContext(tenant_id=tenant_id, user_id=current_user.user_id, role=membership.role)
```

会话内绑定在切换租户时校验一次成员关系，写入会话，之后的请求不再每次查成员。切换走这个专门动作。让客户端改请求头就算切换成功，就退回请求头方案。

两种可以并存：登录时用会话内绑定定下默认租户，同时允许请求头临时声明另一个已加入的租户。两条路径都做成员校验。

## 角色校验

角色校验接在租户上下文之后、业务逻辑之前。角色是租户内的：同一个人在租户 A 可以是管理员，在租户 B 只是成员。

```python
async def require_tenant_admin(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantContext:
    if ctx.role != TenantRole.ADMIN.value:
        raise TenantAdminRequiredException()
    return ctx
```

## 跨租户越权

**改 id。** 请求头或路径仍是自己有权限的租户，请求体或路径里的其他资源 ID 换成别的租户的 ID。repository 不按租户过滤时就能读到。挡住它的是上面的查询过滤。

**批量接口漏过滤。** 单条接口容易记得加过滤。批量导出、批量更新、后台统计，尤其是手写 SQL 或 ORM 的批量方法，容易漏：

```python
# 批量导出忘了租户过滤，导出的是全库
async def export_all_tasks() -> list[Task]:
    return await db.query(Task).all()
```

新增批量、导出、统计接口时，`tenant_id` 过滤和单条查询一样要有。

**后台接口绕过租户维度。** 运营后台可以跨租户查看，这是后台自己的用例。无租户限制的查询与业务侧必须带租户的查询分开：方法名带 `_admin` 或 `_cross_tenant`，只由后台专用 use case 调用。

业务侧与后台共用一个方法、用可选参数决定过不过滤时，新调用点会漏传，隔离就没了：

```python
tenant_id: str | None = None
```
