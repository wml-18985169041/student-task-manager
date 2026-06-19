# GitHub 部署指南 — 学生任务管理系统

> 将本地项目推送至 GitHub，并通过 Render.com 实现线上永久部署，任意设备均可通过公网访问。

---

## 目录

- [1. 前置准备](#1-前置准备)
- [2. 创建 GitHub 仓库](#2-创建-github-仓库)
- [3. 推送代码到 GitHub](#3-推送代码到-github)
- [4. Render.com 线上部署](#4-rendercom-线上部署)
- [5. 后续更新代码](#5-后续更新代码)
- [6. 常见问题](#6-常见问题)

---

## 1. 前置准备

### 注册 GitHub 账号

1. 打开 https://github.com
2. 点击右上角 **Sign up**
3. 填写邮箱、密码、用户名，完成注册

### 确认本地 Git 可用

```bash
git --version
```

> ⚠️ 以下命令均在项目目录下执行：
> ```bash
> cd "C:\Users\31627\Desktop\student-task-manager"
> ```

---

## 2. 创建 GitHub 仓库

1. 打开 https://github.com/new
2. 按以下内容填写：

| 字段 | 填写内容 |
|------|----------|
| **Repository name** | `student-task-manager` |
| **Description** | `学生任务管理系统 - FastAPI + SQLite（多用户版）` |
| **Public / Private** | ✅ 选 **Public** |
| **Add a README file** | ❌ 不勾选 |
| **Add .gitignore** | ❌ 不勾选 |
| **Choose a license** | ❌ 不勾选 |

3. 点击 **Create repository**

---

## 3. 推送代码到 GitHub

```bash
# 1. 添加远程仓库（首次）
git remote add origin https://github.com/<你的用户名>/student-task-manager.git

# 2. 推送
git push -u origin master
```

---

## 4. Render.com 线上部署

> 💡 **为什么要用 Render 而不是 PythonAnywhere？**
> PythonAnywhere 免费版不支持 ASGI（FastAPI），而 Render 完全支持，并且部署更简单。

### 4.1 注册 Render

1. 打开 https://render.com
2. 点击 **Get Started for Free**
3. 选择 **Sign in with GitHub**

### 4.2 创建 Web Service

1. Dashboard → **New +** → **Web Service**
2. 选择 `student-task-manager` 仓库

### 4.3 填写部署配置

| 配置项 | 值 |
|--------|-----|
| **Name** | `student-task-manager` |
| **Region** | `Singapore`（亚洲访问更快） |
| **Branch** | `master` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | ✅ **Free** |

### 4.4 启动部署

点击 **Create Web Service**，等待 2-5 分钟即可获得公网地址：

```
https://student-task-manager.onrender.com
```

---

## 5. 后续更新代码

```bash
git add -A
git commit -m "描述改动内容"
git push
# Render 自动重新部署
```

---

## 6. 常见问题

### Q: 免费实例休眠怎么办？

Render 免费实例 15 分钟无访问会自动休眠，下次访问需 30-60 秒唤醒。用 [UptimeRobot](https://uptimerobot.com) 设置每 5 分钟 ping 一次可防休眠。

### Q: 数据库数据会丢失吗？

免费实例的 SQLite 在重启/休眠时可能丢失数据。如需持久化可升级到 Render 付费计划或迁移到 PostgreSQL。

### Q: 如何查看 API 文档？

启动后访问 `https://你的地址/docs` 即可查看 Swagger UI。

---

> 📋 **项目本地路径**：`C:\Users\31627\Desktop\student-task-manager\`
>
> 📄 **完整项目文档**：[项目文档.md](项目文档.md)
>
> 🐍 **后端代码**：[main.py](main.py)
>
> 🌐 **前端页面**：[static/index.html](static/index.html)
