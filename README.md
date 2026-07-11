# 贴吧热门漏斗图 📊

每 2 小时自动抓取百度贴吧「大家都在逛的吧」列表，生成**手机适配漏斗图**页面，通过 GitHub Pages 提供永久链接访问。

👉 **效果预览**：打开 `https://<你的GitHub用户名>.github.io/<仓库名>/` 即可看到漏斗图。

---

## 为什么不需要 Docker？

GitHub Actions 的 **Ubuntu runner** 是一台预装好 Python、curl、git 等工具的托管虚拟机。你把代码推上去，它按时自动执行 —— 不需要你提供 Docker 镜像，不需要你的电脑开机，完全在 GitHub 的云端机器上运行。

```
你的任务：推送代码 + 设置 Cookie → GitHub 自动搞定一切
```

---

## 快速开始（约 5 分钟）

### 1. 创建 GitHub 仓库

在 [GitHub](https://github.com/new) 新建一个**公开**仓库（名称随意，例如 `tieba-hot`）。

### 2. 获取 Cookie

打开浏览器，访问 `https://tieba.baidu.com/?menu=true`（确保已登录百度账号）。

按 `F12` → **Application** (或 **存储**) → **Cookies** → `tieba.baidu.com`，记录以下三个值：

| Cookie 名 | 位置 |
|-----------|------|
| `BAIDUID` | `.baidu.com` 或 `tieba.baidu.com` |
| `TIEBA_SID` | `tieba.baidu.com` |
| `TIEBA_NEW_PC` | `tieba.baidu.com` |

> 💡 也可以从 `www.baidu.com` 的 cookie 里多拿一个 `BIDUPSID`（非必须，但有的话带上更好）。

### 3. 设置 GitHub Secret

在仓库页面：**Settings** → **Secrets and variables** → **Actions** → **New repository secret**

- **Name**: `TIEBA_COOKIE`
- **Value**: `BAIDUID=你的值; TIEBA_SID=你的值; TIEBA_NEW_PC=1` （用分号+空格分隔）

### 4. 推送代码

```bash
# 在当前目录初始化 Git 并推送
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

### 5. 启用 GitHub Pages

在仓库页面：**Settings** → **Pages**

- **Source**: `GitHub Actions`

保存后，首次部署会自动触发（或手动在 **Actions** 标签页运行一次 `Crawl Tieba & Deploy`）。

### 6. 访问你的链接

部署完成后，链接格式为：
```
https://你的用户名.github.io/仓库名/
```

在手机浏览器打开即可看到漏斗图。

---

## 漏斗图说明

| 概念 | 含义 |
|------|------|
| **累计观测** | 从首次运行至今的总观测小时数 |
| **快照次数** | 一共抓取了多少次数据 |
| **存在时间** | 该吧在所有快照中出现次数 × 2 小时 |
| **百分比** | 该吧存在时间占总观测时间的比例 |
| **其他** | 存在时间不足 1% 的吧合集 |

条形图从上到下按存在时间降序排列，形成**漏斗形状** —— 顶部是「常青树」贴吧，底部是昙花一现的贴吧。随着数据积累（数天到数周），漏斗会越来越明显。

---

## 更新 Cookie

Cookie 大约每 **1-3 个月** 过期。当 GitHub Actions 运行失败时：

1. 打开浏览器访问 `https://tieba.baidu.com/?menu=true`
2. F12 → Application → Cookies，重新获取 `TIEBA_SID`（`BAIDUID` 有效期较长，通常不需要更新）
3. 在仓库 **Settings → Secrets → Actions** 更新 `TIEBA_COOKIE`
4. 手动触发一次 Actions 运行验证

---

## 文件结构

```
.
├── crawler.py              # 爬虫脚本：签名 → 抓取 → 历史管理 → HTML 生成
├── history.json            # 历史快照（自动更新，由 Actions 维护）
├── index.html              # 漏斗图页面（自动生成，由 Actions 维护）
├── .github/
│   └── workflows/
│       └── crawl.yml       # GitHub Actions 定时调度配置
├── .gitignore
└── README.md
```

---

## 技术细节

- **API**: 百度贴吧 `homeSidebarLeft` 端点，PC 端签名算法（MD5）
- **调度**: GitHub Actions cron `0 */2 * * *`（每 2 小时）
- **数据保留**: 自动删除超过 365 天的快照
- **前端**: 纯 HTML + CSS，无框架依赖，适配 320px~640px 屏幕
