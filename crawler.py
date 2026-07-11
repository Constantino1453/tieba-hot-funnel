#!/usr/bin/env python3
"""百度贴吧「大家都在逛的吧」定时爬虫 + 漏斗图 HTML 生成

每运行一次：
  1. 调用 homeSidebarLeft API 获取当前热门贴吧列表
  2. 追加新快照到 history.json
  3. 删除超过 365 天的旧快照
  4. 计算每个吧的「一年内累计存在时间」
  5. 将存在时间 <1% 的吧合并为「其他」
  6. 生成 index.html（手机适配漏斗图）
"""

import hashlib
import io
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

# Windows 控制台 UTF-8 支持
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# ── 配置 ────────────────────────────────────────────────
API_URL = "https://tieba.baidu.com/c/f/pc/homeSidebarLeft"
SECRET_PC = "36770b1f34c9bbf2e7d1a99d2b82fa9e"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
HISTORY_FILE = "history.json"
INDEX_FILE = "index.html"
MAX_AGE_DAYS = 365
MERGE_THRESHOLD = 0.01  # 1% — 低于此比例的吧合并为「其他」

# ── Cookie ──────────────────────────────────────────────
# 从环境变量 TIEBA_COOKIE 读取，格式: "BAIDUID=xxx; TIEBA_SID=yyy; ..."
COOKIE_STR = os.environ.get("TIEBA_COOKIE", "").strip()


def make_sign(params: dict) -> str:
    """生成百度贴吧 API 签名（MD5）"""
    sorted_keys = sorted(params.keys())
    sign_str = "".join(f"{k}={params[k]}" for k in sorted_keys)
    sign_str += SECRET_PC
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest()


def fetch_hot_forums() -> list[dict]:
    """调用贴吧 API 获取「大家都在逛的吧」列表"""
    params = {"_client_type": "20", "subapp_type": "pc"}
    params["sign"] = make_sign(params)
    url = API_URL + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Referer": "https://tieba.baidu.com/?menu=true",
        "Cookie": COOKIE_STR,
    })

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 请求 API...")
    resp = urllib.request.urlopen(req, timeout=20)
    body = resp.read().decode("utf-8")
    data = json.loads(body)

    errno = data.get("errno", 0)
    if errno != 0:
        errmsg = data.get("errmsg", body[:200])
        raise RuntimeError(f"API 返回错误 errno={errno}: {errmsg}")

    forums = []
    for item in data["data"].get("recom_forum_list", []):
        forums.append({
            "id": item.get("id"),
            "name": item.get("name", ""),
            "avatar": item.get("avatar", ""),
            "member_num": item.get("member_num", 0),
            "post_num": item.get("post_num", 0),
            "slogan": item.get("slogan", ""),
        })

    print(f"  获取到 {len(forums)} 个热门贴吧")
    return forums


def load_history() -> list[dict]:
    """从文件读取历史快照"""
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return []
        return json.loads(content)


def save_history(snapshots: list[dict]):
    """写入历史快照到文件"""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshots, f, ensure_ascii=False, indent=2)


def cleanup_history(snapshots: list[dict]) -> list[dict]:
    """删除超过 MAX_AGE_DAYS 天的旧快照"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    kept = [s for s in snapshots if parse_ts(s["ts"]) > cutoff]
    removed = len(snapshots) - len(kept)
    if removed:
        print(f"  清理了 {removed} 条超期快照（>{MAX_AGE_DAYS}天）")
    return kept


def parse_ts(ts: str) -> datetime:
    """解析 ISO8601 时间戳，兼容旧格式"""
    # Python 3.11+ 支持 Z 后缀，这里手动处理兼容
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def compute_funnel(snapshots: list[dict]) -> dict:
    """根据历史快照计算每个吧的累计存在时间，生成漏斗图数据"""
    # forum_key = f"{id}|{name}" -> total_hours
    presence: dict[str, float] = {}
    # latest snapshot data for display names/avatars
    latest_info: dict[str, dict] = {}

    for snap in snapshots:
        seen_ids = set()
        for forum in snap.get("forums", []):
            key = f"{forum['id']}|{forum['name']}"
            presence[key] = presence.get(key, 0) + 2.0  # 每快照代表 2 小时
            seen_ids.add(key)
            # 保留最新的元数据
            if key not in latest_info or snap["ts"] > latest_info[key].get("_ts", ""):
                latest_info[key] = {
                    "id": forum["id"],
                    "name": forum["name"],
                    "avatar": forum["avatar"],
                    "member_num": forum.get("member_num", 0),
                    "slogan": forum.get("slogan", ""),
                    "_ts": snap["ts"],
                }

    if not presence:
        return {"items": [], "total_hours": 0, "other_hours": 0}

    total_hours = len(snapshots) * 2.0

    # 排序：按存在时间降序
    sorted_items = sorted(presence.items(), key=lambda x: x[1], reverse=True)

    # 分离：>=1% 的独立展示，<1% 的合并为「其他」
    threshold = total_hours * MERGE_THRESHOLD
    main_items = []
    other_hours = 0.0
    other_count = 0

    for key, hours in sorted_items:
        if hours >= threshold:
            info = latest_info[key]
            main_items.append({
                "name": info["name"],
                "hours": round(hours, 1),
                "pct": round(hours / total_hours * 100, 1),
                "avatar": info["avatar"],
                "member_num": info["member_num"],
                "slogan": info.get("slogan", ""),
            })
        else:
            other_hours += hours
            other_count += 1

    if other_hours > 0:
        main_items.append({
            "name": f"其他（{other_count}个吧）",
            "hours": round(other_hours, 1),
            "pct": round(other_hours / total_hours * 100, 1),
            "avatar": "",
            "member_num": 0,
            "slogan": "存在时间不足 1% 的吧合集",
        })

    return {
        "items": main_items,
        "total_hours": round(total_hours, 1),
        "snapshot_count": len(snapshots),
        "other_hours": round(other_hours, 1),
    }


def build_html(funnel: dict) -> str:
    """生成自包含的移动适配漏斗图 HTML 页面"""
    items_json = json.dumps(funnel["items"], ensure_ascii=False)
    total_hours = funnel["total_hours"]
    snapshot_count = funnel["snapshot_count"]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    # 找出最大小时数用于条形比例
    max_hours = max((item["hours"] for item in funnel["items"]), default=1)

    # 生成条形 HTML
    bars_html_parts = []
    for i, item in enumerate(funnel["items"]):
        width_pct = (item["hours"] / max_hours * 100) if max_hours > 0 else 0
        is_other = item["name"].startswith("其他")
        avatar_html = ""
        if item["avatar"] and not is_other:
            avatar_html = f'<img class="bar-avatar" src="{item["avatar"]}" alt="" loading="lazy">'
        bars_html_parts.append(f"""\
        <div class="bar-row{" bar-other" if is_other else ""}">
          <div class="bar-label">
            {avatar_html}
            <div class="bar-name-wrap">
              <span class="bar-name">{item["name"]}</span>
              {f'<span class="bar-slogan">{item["slogan"]}</span>' if item["slogan"] and not is_other else ""}
            </div>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width:{width_pct:.1f}%"></div>
          </div>
          <div class="bar-value">
            <span class="bar-hours">{item["hours"]}h</span>
            <span class="bar-pct">{item["pct"]}%</span>
          </div>
        </div>""")

    bars_html = "\n".join(bars_html_parts)

    return f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>贴吧热门漏斗图</title>
<style>
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans SC",sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding:16px}}
  .header{{text-align:center;padding:20px 0 12px}}
  .header h1{{font-size:1.25rem;font-weight:700;color:#f1f5f9;letter-spacing:.02em}}
  .header .meta{{font-size:.75rem;color:#94a3b8;margin-top:6px}}
  .header .meta span{{margin:0 6px}}
  .funnel{{max-width:640px;margin:0 auto;padding-bottom:40px}}
  .bar-row{{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #1e293b}}
  .bar-row.bar-other{{border-top:2px dashed #475569;margin-top:8px;padding-top:12px;opacity:.75}}
  .bar-label{{flex:0 0 120px;min-width:0;display:flex;align-items:center;gap:6px}}
  .bar-avatar{{width:28px;height:28px;border-radius:50%;object-fit:cover;flex-shrink:0;background:#1e293b}}
  .bar-name-wrap{{min-width:0}}
  .bar-name{{font-size:.8rem;font-weight:600;color:#f8fafc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}}
  .bar-slogan{{font-size:.65rem;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}}
  .bar-track{{flex:1;height:20px;background:#1e293b;border-radius:10px;overflow:hidden;min-width:40px}}
  .bar-fill{{height:100%;border-radius:10px;background:linear-gradient(90deg,#3b82f6,#8b5cf6);transition:width .4s ease;min-width:4px}}
  .bar-row:nth-child(1) .bar-fill{{background:linear-gradient(90deg,#f59e0b,#ef4444)}}
  .bar-row:nth-child(2) .bar-fill{{background:linear-gradient(90deg,#f59e0b,#f97316)}}
  .bar-row:nth-child(3) .bar-fill{{background:linear-gradient(90deg,#fbbf24,#f59e0b)}}
  .bar-row.bar-other .bar-fill{{background:#475569}}
  .bar-value{{flex:0 0 auto;text-align:right;display:flex;flex-direction:column;gap:1px}}
  .bar-hours{{font-size:.75rem;font-weight:700;color:#e2e8f0;white-space:nowrap}}
  .bar-pct{{font-size:.65rem;color:#64748b;white-space:nowrap}}
  .footer{{text-align:center;padding:20px 0;font-size:.7rem;color:#475569}}
  @media (max-width:400px){{
    .bar-label{{flex:0 0 100px}}
    .bar-name{{font-size:.72rem}}
    .bar-value{{flex:0 0 52px}}
    .bar-hours{{font-size:.7rem}}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 贴吧「大家都在逛」漏斗图</h1>
  <div class="meta">
    <span>🕐 累计观测 {total_hours} 小时</span>
    <span>📸 {snapshot_count} 次快照</span>
    <span>📅 更新于 {now_str}</span>
  </div>
</div>
<div class="funnel">
{bars_html}
</div>
<div class="footer">
  数据来源：百度贴吧 · 每 2 小时自动更新 · GitHub Actions
</div>
</body>
</html>"""


def main():
    print(f"=== 贴吧爬虫启动 {datetime.now().isoformat()} ===")

    if not COOKIE_STR:
        print("❌ 环境变量 TIEBA_COOKIE 未设置，退出")
        sys.exit(1)

    # 1. 抓取当前热门贴吧
    try:
        forums = fetch_hot_forums()
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        sys.exit(1)

    # 2. 加载历史
    snapshots = load_history()
    print(f"  历史快照: {len(snapshots)} 条")

    # 3. 追加快照
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshots.append({"ts": now_ts, "forums": forums})

    # 4. 清理超期快照
    snapshots = cleanup_history(snapshots)

    # 5. 保存
    save_history(snapshots)

    # 6. 计算漏斗数据
    funnel = compute_funnel(snapshots)
    print(f"  漏斗图: {len(funnel['items'])} 个条目 (含{'其他' if funnel['other_hours'] > 0 else '无其他'})")

    # 7. 生成 HTML
    html = build_html(funnel)
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  已生成 {INDEX_FILE} ({len(html)} bytes)")

    print("=== 完成 ===")


if __name__ == "__main__":
    main()
