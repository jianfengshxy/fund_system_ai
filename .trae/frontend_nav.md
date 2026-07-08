# 前端开发 - 导航指南

## 概述
`frontend/` 是项目的前端展示层，使用 Vue 3 + TypeScript + Vite + Element Plus 技术栈。

## 目录结构
```
frontend/
├── public/                    # 静态资源
│   ├── favicon.svg
│   └── icons.svg
├── src/                      # 源码目录
│   ├── assets/              # 资源文件
│   │   ├── hero.png
│   │   └── ...
│   ├── components/          # 组件
│   │   └── HelloWorld.vue
│   ├── App.vue              # 主应用组件
│   ├── main.ts              # 应用入口
│   └── style.css            # 全局样式
├── .env.development         # 开发环境变量
├── .env.production          # 生产环境变量
├── vite.config.ts           # Vite配置
├── tsconfig.json            # TypeScript配置
├── eslint.config.js         # ESLint配置
├── .prettierrc              # Prettier配置
└── package.json             # 依赖配置
```

## 技术栈
- **框架**: Vue 3 (Composition API)
- **语言**: TypeScript
- **构建工具**: Vite
- **UI组件库**: Element Plus
- **样式工具**: Tailwind CSS
- **HTTP客户端**: Axios
- **代码规范**: ESLint + Prettier

## 开发命令
| 命令 | 说明 |
|------|------|
| `cd frontend && npm install` | 安装依赖 |
| `npm run dev` | 启动开发服务器 |
| `npm run build` | 构建生产版本 |
| `npm run lint` | 运行ESLint检查 |
| `npm run lint:fix` | 自动修复ESLint问题 |
| `npm run format` | 使用Prettier格式化代码 |

## 环境变量
- `.env.development`: 开发环境配置
- `.env.production`: 生产环境配置

## 与后端通信
前端通过API与Flask后端通信，开发环境通过Vite proxy转发到本地后端9000端口。
