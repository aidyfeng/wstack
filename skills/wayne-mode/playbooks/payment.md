# 支付

先看谁掌管下单、订阅和到账，再决定打不打开 `standard-payment-integration`。

## 自托管：用该技能

项目自己对接渠道，自己验签、查单、对账时，读 `standard-payment-integration`。常见是应用内购的服务端通知、移动端代扣、网页一次性下单，几种通道可以并存。领域模型要能区分「能代扣」和「只能一次性付款」。只接一种通道时，只用该技能里和这种通道有关的条款。

权益是否到账由业务用例决定。这篇管下单、验签、查单和对账。会话谁签发见 [login](login.md)。

## Stripe 或 RevenueCat：不用该技能

这两家自己掌管支付和订阅。不要读 `standard-payment-integration`，也不要把自建通道模型搬过去：渠道能力矩阵、自己验签、自己查单对账。

**Stripe** 按 Stripe 自己的最佳实现做，用 `stripe-best-practices`。

**RevenueCat** 按 RevenueCat 自己的最佳实现做（Purchases SDK、webhook、entitlement）。本仓库没有 RevenueCat 专篇。

支付方案还没定时先问，不要默认套自托管通道。
