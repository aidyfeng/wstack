# 前端交付物

先看页面给谁用，再选技能。不要把用户应用写回 Next.js。

| 页面 | 应用 | 技能 |
| --- | --- | --- |
| 官网、公开协议、旧用户 URL 重定向 | `ui/apps/site`（Next.js） | 无专篇。只改这个站点，不要套用户应用的技能 |
| 登录、设置、会员，以及其余用户页面，含浏览器里的网页版 | `ui/apps/mobile`（Expo Router，iOS / Android / Web） | `standard-react-native-app` |
| 运营后台 | `ui/apps/admin` | `standard-react-ops-console` |
| 微信小程序 | `ui/apps/client` | `standard-taro-miniprogram` |

网页版、安卓、iOS 是 `ui/apps/mobile` 这一个 Expo 工程，部署到 `app.example.com`。不要写成 Next 的 `(app)` 区。

`pnpm web` 在浏览器打开网页版。`pnpm start` 给安卓和 iOS 用。本仓库有 `expo-dev-client`，手机装 Development Build，应用商店里的 Expo Go 打不开。没有这个依赖的项目才用 Expo Go 同时扫安卓和 iOS。

四端都适用的 React 写法（React Query、不要全局 store）见 `standard-react-conventions`。跨 app 的包边界见 `standard-frontend-monorepo`。
