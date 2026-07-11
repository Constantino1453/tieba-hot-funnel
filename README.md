# 贴吧热门漏斗图 📊

每 2 小时自动抓取百度贴吧「大家都在逛的吧」列表，生成**手机适配漏斗图**页面，通过 GitHub Pages 提供永久链接访问。

👉 **效果预览**：打开 `https://<你的GitHub用户名>.github.io/<仓库名>/` 即可看到漏斗图。

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
