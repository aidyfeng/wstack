# 项目结构

## 后端

一个 FastAPI 代码库，两个入口：面向用户的服务和运营后台。入口文件只选择挂哪些路由。分层、UseCase、依赖注入读 `standard-fastapi-ddd-backend`。

每个业务模块四层：`domain/`、`application/`、`infrastructure/`、`presentation/`。用例放在 `application/use_cases/`。

表和迁移不在这篇展开，见 [persistence](persistence.md)。

## 前端

pnpm workspace 在 `ui/`。页面进哪个 app 见 [frontend](frontend.md)。

```
ui/
├── apps/{site,admin,client,mobile}
└── packages/    共享包：core、api、tokens、ui-web、platform、config
```

代码放进共享包还是留在 app，读 `standard-frontend-monorepo`。
