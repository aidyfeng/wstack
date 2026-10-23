# 网页与 App

先看页面给谁用，再选技能。用户应用的网页版、安卓、iOS 是同一个 Expo 工程，不写进 Next.js。

## 网页

| 页面 | 应用 | 技能 |
| --- | --- | --- |
| 官网、公开协议、旧用户 URL 重定向 | `ui/apps/site`（Next.js） | 无专篇。只改这个站点 |
| 用户页面在浏览器里的网页版 | `ui/apps/mobile` | `standard-react-native-app` |
| 运营后台 | `ui/apps/admin` | `standard-react-ops-console` |

`pnpm web` 在浏览器打开用户应用的网页版，部署到 `app.example.com`。官网继续留在 `ui/apps/site`。

四端通用的 React 写法（React Query、不设全局 store）用 `standard-react-conventions`。包放共享目录还是留在 app 里，用 `standard-frontend-monorepo`。

## App

用户应用的 iOS、Android 和网页版都在 `ui/apps/mobile`（Expo Router）。技能是 `standard-react-native-app`。

`pnpm start` 给安卓和 iOS。本仓库有 `expo-dev-client`，手机装 Development Build，应用商店里的 Expo Go 打不开。没有这个依赖的项目才用 Expo Go 同时扫安卓和 iOS。

微信小程序不是这个 App。它在 `ui/apps/client`，技能是 `standard-taro-miniprogram`。小程序只出微信，不拿它的 H5 产物当网页版。
