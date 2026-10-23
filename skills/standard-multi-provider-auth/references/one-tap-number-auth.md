# 运营商一键取号接入指南

> **定位**：`SKILL.md` ⑦ 提到"一键取号优先、短信兜底"，本文是那条通道的**通用接入知识**——
> 换个项目再接一次同样适用。项目自己用了哪个厂商方案、密钥放在哪，属于对账信息，在
> `project-bindings.md`。

中国大陆运营商提供「本机号码一键登录」：客户端 SDK 取到一个一次性 token，服务端拿 token
换回真实手机号。运营商侧已经验证过号码归属，**等价于短信 OTP 已通过**。

下面的实测结论来自阿里云号码认证服务（PNVS），其它厂商（腾讯云、极光等）机制同构，但
**码值和 API 名一定不同，不要照抄常量**。

---

## ① 选型：号码认证 ≠ 融合认证

厂商控制台通常会并列摆着「号码认证」和「融合认证」两个产品。

**已有自建短信链路的项目一律选号码认证。** 融合认证会把短信验证码也托管到厂商侧，于是
同一个"手机号 + 验证码"在 App 和 Web 走两套验证体系，OTP 存储、限流、风控、告警全部分叉。
融合认证是给"从零开始、不想自建短信"的项目省事用的。

计费参考：一键登录约 ¥0.04/次（10 万–500 万档），与本机号码校验合并计费。**需要企业实名**，
个人实名账号只能用短信认证。

---

## ② ★★ 一手真理源是二进制里的头文件，不是网页文档

拿到真实 SDK 后逐条核对，**查出 6 处会导致编译或运行失败的错误——其中一处正是照着网页
文档改出来的**。接入前先把接口签名从二进制里挖出来：

```bash
# iOS：framework 内自带完整头文件
ls XxxSDK.xcframework/ios-arm64/XxxSDK.framework/Headers/
#   返回码全量、主 API、授权页属性各一个头文件

# Android：javap 反编译 aar
unzip -q xxx.aar && unzip -q classes.jar -d cls
javap -classpath cls -constants com.example.ResultCode      # -constants 才能看到码值
javap -classpath cls com.example.PhoneNumberAuthHelper
```

---

## ③ ★★ 两端 API 完全不同，不能互抄

**授权页定制**：iOS 走一个 model 对象的属性，Android 走 Builder setter，命名毫无对应关系。
照 Android 命名写 iOS，实测 17 个属性里 **13 个不存在**。iOS 侧几个反直觉的地方：

- 标题、按钮文案是 `NSAttributedString`，颜色走 attributes，**没有单独的 textColor 属性**
- **登录按钮没有背景色属性**，只有背景图数组，纯色也得现画一张图
- 圆角属性根本不存在

**环境检查的成功码两端不一样**：Android 有一个专用的"环境检查成功"码，iOS 的返回码头文件里
**根本没有这个码**，成功就是通用成功码。网页文档讲的是 Android 那套。
★★ **照网页文档给 iOS 写 Android 的码 → 可用性探测恒为 false → 一键入口永不出现**。
这是静默失败，界面上只是"少了个按钮"，极难查。

**注意同名方法的重载**：Android 的环境检查有两个重载，无参版同步返回 `boolean`（该用这个）；
带参版返回 `void`，结果异步回调到构造 helper 时传入的那个 listener——而那个 listener 正
服务于取号流程的 pending call，会被抢走。

---

## ④ ★★ 回调码：只有一个是终态，listener 会多次回调

| 类别 | 语义 | 处理 |
|---|---|---|
| 取号成功（带 token） | **唯一终态成功码** | 消费 pending call |
| 唤起授权页成功 | 中间态 | 直接 return |
| 用户点返回 | 取消 | 终态 |
| 用户点「切换其他方式」 | **导向短信，不是取消** | 终态，落短信表单 |
| 点登录按钮 / 勾选框 / 协议 | 中间态 UI 事件 | 直接 return |

★★ **同一次取号，listener 会被回调多次**。踩过的坑：一进回调就消费掉 pending call，授权页
刚弹出（中间态）就以"取消"收场，后续真正带 token 的回调拿到空 call 直接返回 →
**token 永远拿不到**。

Android 侧直接引用 SDK 自带的返回码常量，不要硬编码字符串。

---

## ⑤ iOS：framework 往往不是 modular，Swift 不能直接 import

厂商 framework 内常常**没有 `Modules/module.modulemap`**，且 umbrella header 名与 framework
名对不上，于是 `import XxxSDK` 直接报 "No such module"。

解法：在自己的 pod 里放一个 ObjC 桥接头（`#import <XxxSDK/Umbrella.h>`），CocoaPods 会把它
收进本 pod 的 umbrella header，同 pod 内的 Swift 就不必再写 import。
（备选是给每个 slice 补 modulemap，但升级 SDK 要重做一遍。）

其它实测细节：

- 包内常同时给 `frameworks/`（fat）和 `xcframeworks/` 两份，**取 xcframework**——fat
  framework 的真机与模拟器 arm64 冲突，且提交前必须剥掉模拟器架构，否则上传被拒
  （ITMS-90087）。无人值守流水线不该多这道手工步骤
- 授权页图标资源 bundle 若在 framework 内部，podspec **不要**再写 `s.resources`，写了
  `pod install` 会报找不到资源

---

## ⑥ SDK 只能从控制台下载，不在公共包管理器里

- **iOS**：CocoaPods trunk 上没有官方包；偶尔能搜到同名包，多是多年前个人账号发布的
  单版本，不可信。官方只分发 framework/bundle，走 `s.vendored_frameworks` 本地打包
- **Android**：只有控制台下载的 aar，放 `libs/` 用 `fileTree` 引用
- 二进制**直接入 git** 供 CI 使用（别 gitignore）。CI 里加断言：插件未注册、或二进制缺失
  时当场失败，不要让错误漂到链接期才炸
- Android 包名里的 `static`/`dynamic` 与 iOS 的动静态库不是一回事，官方没说明；实测 static
  版内容与文档一致、可用，且国内商店限制运行时动态加载代码，static 合规角度更稳

---

## ⑦ 密钥

- iOS 与 Android 在控制台是**两个独立方案**，密钥不可混用（混用直接取号失败）
- 密钥性质同各类客户端 AppID：会编进包、本就分发到客户端，且绑定「包名 + 签名指纹」
  (Android) /「Bundle ID」(iOS)，泄露也无法在别的 App 冒用。**但仍要走 secrets、不明文入
  git**——它是长期凭据，要收回得改代码 + 发版
- ★ **密钥留空时必须让可用性探测返回 false、静默不展示一键入口**，直接走短信。不要出死按钮

---

## ⑧ 硬约束（前端降级逻辑依赖这些）

- **必须有蜂窝数据**。纯 WiFi、无 SIM 卡、平板 WiFi 版一律取号失败
- **双卡取到的是默认数据卡的号**，未必是用户想用的那个——这是短信通道不能砍的根本原因
- 部分虚商号段不支持

所以**预取失败绝不能抛异常**，必须优雅落到短信表单。

---

## ⑨ 服务端换号

服务端用 token 换真实号码，注意两点：

- SDK 包名里的日期/版本串容易记错，以控制台文档给出的 artifact 坐标为准
- 若复用项目已有的云厂商 AccessKey，**RAM 子账号要另行授予号码认证的权限**——只有对象
  存储、短信权限的子账号调用会直接 403
