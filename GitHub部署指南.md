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
4. 登录后保持浏览器打开

### 确认本地 Git 可用

打开终端（PowerShell / CMD / Git Bash），执行：

```bash
git --version
```

输出版本号即表示可用。若未安装，前往 https://git-scm.com 下载安装。

> ⚠️ 以下命令均在项目目录下执行：
> ```bash
> cd "C:\Users\31627\Desktop\student-task-manager"
> ```

---

## 2. 创建 GitHub 仓库

### 2.1 新建仓库

1. 打开 https://github.com/new
2. 按以下内容填写：

| 字段 | 填写内容 |
|------|----------|
| **Repository name** | `student-task-manager` |
| **Description** | `学生任务管理系统 - FastAPI + SQLite` |
| **Public / Private** | ✅ 选 **Public**（免费私有部署） |
| **Add a README file** | ❌ 不勾选 |
| **Add .gitignore** | ❌ 不勾选 |
| **Choose a license** | ❌ 不勾选 |

3. 点击绿色按钮 **Create repository**

### 2.2 复制仓库地址

创建完成后页面会显示一个 URL，点击 📋 复制按钮：

```
https://github.com/<你的用户名>/student-task-manager.git
```

类似：`https://github.com/zhangsan/student-task-manager.git`

> 🔄 **记下这行地址**，下一步要用。

---

## 3. 推送代码到 GitHub

### 3.1 配置 Git 身份（首次使用 Git 需要）

```bash
git config user.name "你的GitHub用户名"
git config user.email "你的GitHub邮箱"
```

### 3.2 添加远程仓库并推送

依次执行以下命令：

```bash
# 1. 添加远程仓库地址（替换为你的地址）
git remote add origin https://github.com/<你的用户名>/student-task-manager.git

# 2. 推送代码
git push -u origin master
```

### 3.3 GitHub 身份验证

执行 `git push` 后可能弹出登录窗口或要求输入凭据：

**方式一：浏览器弹窗（推荐）**
- 自动弹出 GitHub 授权页面 → 点击 **Authorize**

**方式二：Token 认证**
1. 打开 https://github.com/settings/tokens
2. 点击 **Generate new token (classic)**
3. 勾选 `repo` 权限，生成 Token
4. 复制 Token 作为密码粘贴到终端

### 3.4 验证推送结果

刷新 GitHub 仓库页面，应看到以下文件：

```
📁 student-task-manager/
├── 📄 main.py
├── 📄 requirements.txt
├── 📄 .gitignore
└── 📁 static/
    └── 📄 index.html
```

---

## 4. Render.com 线上部署

### 4.1 注册 Render

1. 打开 https://render.com
2. 点击 **Get Started for Free**
3. 选择 **Sign in with GitHub**（用 GitHub 账号授权登录）

### 4.2 创建 Web Service

1. 进入 Dashboard，点击右上角 **New +** 按钮
2. 下拉菜单选择 **Web Service**
3. 在仓库列表中找到并点击 `student-task-manager`
   > 若看不到，点击 **Configure account** 给 Render 授权访问该仓库

### 4.3 填写部署配置

| 配置项 | 填写内容 |
|--------|----------|
| **Name** | `student-task-manager`（可自定义） |
| **Region** | `Singapore`（亚洲访问更快） |
| **Branch** | `master` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | ✅ **Free**（免费） |

其余选项保持默认。

### 4.4 启动部署

1. 页面底部点击 **Create Web Service**
2. 等待 2-5 分钟，日志区域实时显示部署进度
3. 看到 `Your service is live` 即表示部署成功

### 4.5 获取公网地址

部署成功后，页面顶部显示公网 URL：

```
https://student-task-manager.onrender.com
```

🎉 **用手机/平板/任意设备打开这个链接即可使用！**

---

## 5. 后续更新代码

当你修改了本地代码，按以下步骤更新线上：

```bash
# 1. 进入项目目录
cd "C:\Users\31627\Desktop\student-task-manager"

# 2. 暂存所有修改
git add -A

# 3. 提交（修改提交信息描述本次改动）
git commit -m "描述你改了什么"

# 4. 推送到 GitHub
git push

# 5. Render 会自动检测到推送，自动重新部署（无需手动操作）
```

整个过程约 2-3 分钟，Render 自动完成。

---

## 6. 常见问题

### Q1: `git push` 报错 `remote origin already exists`

```bash
# 先删除旧地址，再重新添加
git remote remove origin
git remote add origin https://github.com/<你的用户名>/student-task-manager.git
git push -u origin master
```

### Q2: 忘记 GitHub 用户名

打开 https://github.com ，右上角头像旁边的名字就是你的用户名。或者访问 https://github.com/settings/profile 查看。

### Q3: Render 部署后访问空白/报错

1. 打开 Render Dashboard → 点击你的服务
2. 查看 **Logs** 标签页的错误日志
3. 确认 Start Command 为 `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Q4: 免费实例休眠怎么办

Render 免费实例 15 分钟无访问会自动休眠，下次访问需 30-60 秒唤醒。

**解决方案**：用 [UptimeRobot](https://uptimerobot.com)（免费）设置每 5 分钟 ping 一次你的 URL，防止休眠。

### Q5: 数据库数据会丢失吗

Render 免费实例的 SQLite 文件存储在临时磁盘上，**重启/休眠时可能丢失数据**。如需持久化：

- 升级到 Render 付费计划（$7/月起，带持久磁盘）
- 或将数据库迁移到 Render PostgreSQL（有免费额度）

---

> 📋 **项目本地路径**：`C:\Users\31627\Desktop\student-task-manager\`
>
> 📄 **完整项目文档**：[项目文档.md](C:\Users\31627\Desktop\student-task-manager\项目文档.md)
>
> 🐍 **后端代码**：[main.py](C:\Users\31627\Desktop\student-task-manager\main.py)
>
> 🌐 **前端页面**：[index.html](C:\Users\31627\Desktop\student-task-manager\static\index.html)
