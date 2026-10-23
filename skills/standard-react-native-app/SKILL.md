---
name: standard-react-native-app
description: >
  Expo 应用。写用户应用页面或浏览器网页版、接原生能力、在手机上打开开发客户端、配构建签名与版本号、处理 iPad，或选择 OTA 与商店发版时使用。
---

# Expo 应用

预设 Expo（含 EAS）+ pnpm workspace 共享包。不覆盖裸 RN 工程。

## 与小程序端的 features 同构

两端 `features/` 同名、同结构：一样的 feature 名，一样的 `hooks/`、`services/`、`components/`。

`hooks/` 和 `services/` 不 import `react-native`。原生能力经 `platform/`。这样两端差异只剩组件层。宿主无关的总则见 `standard-react-conventions`。

## 版本矩阵用官方组合

Expo 每个 SDK 对应特定的 React 与 React Native 版本。用官方 CLI 初始化，或用 `expo install` 装依赖，让它决定版本。

手写「最新版」会装出 Expo 不支持的组合。SDK 57 对应 RN 0.86.x，npm 上的最新是 0.87.x。不匹配往往是运行时的诡异错误，不是安装期报错。

升级 SDK 走 `expo install --fix`，不逐个包手改版本号。

## 三端

网页、安卓、iOS 是同一个 Expo 工程。`app.json` 的 `platforms` 同时有 `ios`、`android`、`web`。同一份 `src/app` 跑三端。

`pnpm start` 起开发服务器，安卓和 iOS 连这一台。`pnpm web` 在浏览器打开网页版（`react-native-web`）。网页版不在手机上的 Expo Go 里跑。

本仓库依赖 `expo-dev-client`。手机客户端是 Development Build：`expo run:android` / `expo run:ios`，或 EAS 的 development profile。应用商店里的 Expo Go 打不开这个工程。只改 JS 时 Metro 热更新，不必重装；原生依赖变了才重建这个客户端。

没装 `expo-dev-client` 的项目用 Expo Go，安卓和 iOS 一起扫。商店版 Expo Go 会落后于新 SDK，扫码可能报 `Project is incompatible with this version of Expo Go`。装新版 Expo Go。确实没有，再降 SDK，并且走 `npx expo install --fix`，不手写 expo / react / react-native 的版本组合。

三端都启用时保留 `platforms` 和 Web 配置。Web 与原生的差异用平台文件或 `platform/` 实现。只做原生的项目不必打开 Web。DOM 组件不导入原生界面。路由器用项目里已经在用的那种。

## 原生能力经 platform/

`features/*` 里的原生能力都先包一层，放 `platform/`。不在 feature 里直接 import 原生模块。

1. **可用性探测**：模块不存在或当前平台不支持时，`isAvailable()` 返回 false，不抛错、不崩。
2. **降级写在文件头**：不可用时是静默 no-op、返回兜底值，还是上抛给调用方。
3. **能拆成纯函数的拆出去**，并标注「纯模块，不依赖原生桥」，这样可以直接单测。

用户主动触发的操作失败要上抛（登录、购买、分享）。用户点了按钮，什么都不发生比报错更糟。

后台或装饰性操作失败可以静默（埋点、预取、媒体元数据上报）。注释里写明 `fire-and-forget`，和掩盖故障分开。

第三方 SDK 的 appid / 密钥没注入时，对应入口不展示。展示一个必然失败的按钮，点了也完不成。配置遗漏本身也不会报警：来源项目 CI 漏注入微信 appid，登录页的微信入口整个消失，排查很久才发现不是代码。接同类能力时在注释里写下选了哪一种（死按钮或静默消失）以及为什么。

## iOS：marketing version 与 build number

- **marketing version**（商店显示的版本号）只支持三段 `MAJOR.MINOR.PATCH`。版本号来源是四段时，取前三段。Apple 不识别第四段。
- **build number** 在同一 marketing version 下递增且不重复。查商店里该 marketing version 当前的最大 build number，再 +1。其他平台的版本编码公式在 marketing version 不变时会反复算出同一个数字，撞号被拒。

marketing version 一旦上架，这个号永久关闭。再传任何新 build 都会被拒。build number 递增救不了，商店卡的是 marketing version 这个字段。

构建可以全程正常，卡在最后一步上传被拒，前面的构建资源已经消耗完。发布前确认目标版本号没上架过。

## Android 签名

```
优先级：本地 keystore 文件 > 环境变量 > 未签名兜底（仅警告，不阻断）
```

签名凭据不硬编码进配置，keystore 不进版本控制。两者都缺失时，构建退化为未签名包并警告，不失败。否则没配凭据的开发环境连日常构建都跑不了。

第三方 SDK 要求签名指纹一致时（微信登录等），debug 变体在检测到本地凭据时可以复用 release 签名。CI 和其他开发者不受影响。

EAS Build 走托管凭据时，这套优先级由 EAS 管理。本地 prebuild 构建仍按上面的优先级。

## iPad

Expo 模板里 `ios.supportsTablet` 默认为 true。开着但 UI 没适配，结果是全屏拉伸（1024pt 宽的按钮、单列长文本），比关掉后的居中黑边更难看。声明支持之后，审核员会用 iPad 测，布局崩了按 2.1 / 4.0 打回。

UI 没适配时把 `ios.supportsTablet` 设为 false。

真要支持，四件都做：

1. `orientation` 不锁 `portrait`。iPad 的 Split View / Slide Over 要求支持所有方向。
2. 响应式：RN 没有 CSS media query，用 `useWindowDimensions()` 按断点分叉布局。
3. 导航：手机底部 tab 在 iPad 上通常改成侧边栏或 split view。
4. 图标和启动图出 iPad 尺寸。

共享包里的业务逻辑 iPad 直接复用，要分叉的只有组件层。不必提前为 iPad 改架构。

iPad 上的 Safari 够用。网页版已经响应式时，原生 iPad 只在需要离线、推送或商店内购通道时单独做。

## Metro

工作区根以 workspace 配置为准。不把仓库根或 `ui/` 写成所有项目的固定路径。

Expo 的 monorepo 自动配置能用就沿用。有显式 Metro 配置时，确认共享源码和依赖的真实路径都在监听和解析范围内，并用目标平台的导出验证。改了目录布局，再查一遍依赖链接。

## 发版

Expo 有两套更新，分开用：

- **EAS Update**（OTA）：只能改 JS 和资源，不能改原生。适合修文案、改逻辑。
- **商店发版**：原生依赖变化、SDK 升级、权限变更走这条。

判据是改动有没有碰到原生层。装了新的原生模块、改了权限声明、升了 SDK，一律商店发版。OTA 推一个和原生层不匹配的 JS 包，启动会崩溃。

有 EAS Update 就用它。自建「比对 CDN 上的 manifest 判断有无新版」是没有 OTA 时的变通，这里不需要。
