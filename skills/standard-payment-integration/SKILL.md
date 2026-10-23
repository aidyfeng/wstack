---
name: standard-payment-integration
description: >
  自托管支付通道。项目自己对接渠道、验签、查单、对账，或处理跨账号恢复购买时使用。
  Stripe 或 RevenueCat 不适用；先看 wayne-mode 的 playbooks/payment.md，按这两家自己的最佳实现做。
---

# 支付通道接入

仅项目自己对接支付渠道时使用。Stripe 或 RevenueCat：停，按 `skills/wayne-mode/playbooks/payment.md` 走它们自己的最佳实现，不要把下面的通道模型搬过去。

多种通道并存或即将并存：应用内购、移动端代扣、网页一次性下单。至少一种通道要做自动续费，模型上区分「能代扣」和「只能一次性付款」。只接单一通道时，只用相关条款。

①–⑦ 与地域无关，海外照用。Apple IAP / Google Play 自带自动续费、平台服务端通知和平台抽成，并且不允许引导用户去站外支付。这四条全球一致。

非内购渠道先查清真实能力再建模。国内常见形态：移动端 SDK 代扣能自动续费，但要走签约；网页一次性下单多数只能一次性支付，自动续费另要商业资质（⑧）。海外订阅型收单在网页侧就能做订阅，没有这道割裂。

## 通道能力写在领域模型上

套餐上标注可售渠道。依据是支付通道的能力，不是前端排不排这个套餐。

```python
@dataclass(frozen=True)
class PlanSpec:
    code: str
    price_cents: int
    period_days: int
    auto_renew: bool
    channels: frozenset[str]  # 可售渠道，按支付通道能力划分——不是按前端排期决定
```

自动续费套餐只出现在支持代扣或内购的渠道。网页一次性下单渠道只卖一次性买断。网页代扣资质批下来之后，改 `channels` 即可开放自动续费，业务逻辑不动。能力判断留在这一处，不散落到 `if channel == "web"`。

下单和签约入口校验这个约束，挡住绕过展示、直接构造请求买不可售套餐：

```python
if command.channel not in plan_spec.channels:
    raise PlanNotAvailableForChannelException(...)
```

通道各自实现自己真正有的操作。一个 Protocol 用 no-op 填满所有通道时，读接口看不出哪些方法生效；加第三种通道时也没有「实现哪些、跳过哪些」的依据：

```python
class PaymentProvider(Protocol):
    async def initiate_sign(self, ...) -> SignInitiation: ...
    async def deduct(self, subscription) -> PaymentOrder | None: ...
        # 内购型：续费由平台自动扣款 + 异步通知驱动，此方法恒 no-op
    async def query_order(self, out_trade_no: str) -> dict | None: ...
        # 内购型：主动对账需要额外的平台 API 凭据，本期未接，恒 no-op
    async def unsign(self, subscription) -> bool: ...
        # 内购型：退订只能用户去系统设置操作，此方法恒 no-op 返回 True
    async def refund(self, subscription) -> bool: ...
        # 一次性下单型：本期未接自助退款 API，退款走人工流程，恒 raise
    async def handle_callback(self, raw_payload: dict) -> PaymentOrder | None: ...
        # 一次性下单型：回调走路由专属分支处理，不经过这个方法，恒 raise
```

正常路径不该调用到不适用的方法。调用到了就是上游分流有 bug：`raise NotImplementedError`，让失败可见；或者返回明确的「不适用」。静默返回成功会把没做成伪装成做成了。

## 幂等键按交易类型分开

同一个平台里，两种交易的稳定字段相反。

非续费（一次性）内购：每次购买的原始交易 id 都会变，不能拿它做幂等键。自动续费：整个签约合同期内原始交易 id 恒定，它就是幂等键。

```python
if plan_spec.auto_renew:
    # 自动续费：整个签约合同期内原始交易 id 恒定，可作幂等键直接反查
    sub = await subs.find_by_contract_id(original_transaction_id)
else:
    # 非续费：每次购买这个 id 都不同，find_by_contract_id 恒查不到——
    # 必须改按 (user_id, 商品编码) 反查该用户已有记录，做「叠加」而非「覆盖」
    sub = await subs.find_by_user_and_plan(user_id, plan_code)
```

幂等命中之后的自愈也分开，不共用一套：

- 自动续费重复提交：用本次交易的到期时间刷新，只推进不回退。正常重复提交不受影响；权益意外落后时能自愈。
- 非续费的到期时间是叠加算出来的，不是权威值。照抄自动续费的自愈，会拿单次交易的到期时间覆盖已经叠加多次的结果。同一笔交易反复提交就能刷权益。非续费幂等命中时只读现状返回，不做写操作。

接入前确认这个交易类型下哪个字段稳定。同一平台的交易类型不共用一个幂等键。两条路径显式分开，不共用 `_is_duplicate()` 或一套通用幂等函数：正确行为是相反的。

## 商户订单号由调用方生成，先落库

一次性下单的 provider 要商户订单号。应用层生成（ULID 一类），先落库，再传给 provider：

```python
out_trade_no = generate_ulid()
order = PaymentOrder(out_trade_no=out_trade_no, status="pending", ...)
await order_repo.save(order)                 # 先落库
redirect = await provider.initiate_sign(..., out_trade_no=out_trade_no)
```

provider 调用失败或超时时，本地仍有一条 pending 订单，可以查、重试、对账。否则钱可能已经扣了，系统里没有痕迹。

代扣型和内购型不用这个参数。购买发生在客户端，没有「我方先生成商户单号再下单」这一步。

## 场景由路由解析后传入

按设备分流的支付页面形态由路由层解析请求，显式传给 use case 和 provider。provider 不读 request。

```python
PaymentScenario = Literal["pc", "wap"]   # 路由解析 UA 得出，显式传入，provider 不读 HTTP request

async def initiate_sign(self, ..., scenario: PaymentScenario | None = None) -> SignInitiation:
    ...
```

provider 只依赖入参，单测可以直接构造调用，后台任务和定时对账也能复用。那些场景没有 HTTP 请求。

## 回调先验签，失败让平台重投

异步回调先验签。签名、金额、受众等字段全部通过，才进业务逻辑。业务逻辑按「同一笔通知会被重复投递」来写。

验签失败或业务处理异常时，按平台约定返回非成功状态，让平台重投。返回成功等于告诉平台已经处理好了：这笔通知不会再来，钱收了，权益发不出去，也没有重试。

## 主动查单，和回调共用结算入口

除了被动回调，还要有 `query_order`。回调丢失是常态：网络抖动、部署窗口重启、平台重试次数耗尽。没有主动查单，付了钱但权益没到，只能等用户投诉后人工翻账。

查会员或查权益状态不能代替查这一笔订单。用户本来已经是会员，再买一单，权益接口第一次轮询就会返回「是会员」，哪怕这笔新单没到账。按订单号向支付平台核实这一笔的状态。

查单结果和回调进同一个结算入口（标记已支付并发放权益）。谁先到都只生效一次。入口自己做并发安全：仅当订单仍是待支付才转已支付。不靠调用方各自判断要不要再处理一次。

## 跨账号恢复购买要决定权益归谁

应用内购绑的是平台账号（如 Apple ID），不是产品自己的用户账号。用户换一个应用账号登录，又在同一台设备上点恢复购买，会出现「订阅属于账号 A，账号 B 想要」的冲突。

验票或验通知时，若这笔交易已经绑了另一个应用账号，显式选一条：直接拒绝，或走人工客服核实后再转移。拒绝时不转移权益，避免后登录的账号顶掉正在使用的付费用户。

不写这条时，常见默认是静默转给最后一次验票的账号。那是可被利用的漏洞。

## 中国大陆：自动续费先确认商业准入

本节只用于中国大陆。海外主流订阅型收单开通账号就能自动续费，整节跳过。

在中国大陆，自动续费（网页代扣或移动端代扣）通常有硬性商业资质：注册资本规模、历史交易流水规模。各支付平台的门槛不互通。这是商业资质，技术方案绕不过去。

选型时先确认资质能不能过，再决定自动续费进不进技术方案。过不了时，先上一次性支付，把自动续费标成「资质就绪后开启」。上面的 `channels` 已经把可售能力收成一个字段，资质到位后改配置，不必重做领域模型。

「先一次性、自动续费标成待开启」在任何能力暂时缺位时都适用，不限于资质。
