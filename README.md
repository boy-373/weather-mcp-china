# Weather Forecast MCP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Remote](https://img.shields.io/badge/Streamable%20HTTP-hosted%20free-success)](https://mcp.pianam.cn/weather-mcp/mcp)

Current weather + up to 7-day forecasts for **cities worldwide** (Chinese and English city names, Chinese output), with dual data sources for reliability.

- **Try it in 30 seconds**: a free public MCP endpoint is already running — just paste the URL into your MCP client (no install, no API key).
- **Or self-host**: a single Python file, stdlib HTTP + FastMCP, zero paid dependencies.

## ⚡ Use the hosted endpoint (no setup)

```
https://mcp.pianam.cn/weather-mcp/mcp
```

Transport: **Streamable HTTP** (MCP 2025-03-26 compatible). No authentication required.

## 🔌 Client configuration

Add this to your MCP client's `mcpServers` configuration (Claude Desktop `claude_desktop_config.json`, Cursor `mcp.json`, Cline, Cherry Studio, etc.):

```json
{
  "mcpServers": {
    "weather": {
      "type": "http",
      "url": "https://mcp.pianam.cn/weather-mcp/mcp"
    }
  }
}
```

> Clients that do not accept `"type": "http"` (some Cherry Studio / older
> Cline versions) accept the same entry with just `"url"`.

## 🧰 Tools

| Tool | Parameters | Returns |
|---|---|---|
| `query_weather(city, days=3)` | `city`: Chinese or English city name, e.g. `"青岛"`, `"北京"`, `"Tokyo"`.<br>`days`: forecast days, 1–7 (default 3). | Current conditions (weather text, temperature, feels-like, humidity, wind direction/speed) + daily forecast (date, weather, high/low, precipitation probability). |

## 📡 Data sources, caching & limits

- Primary source: **[Open-Meteo](https://open-meteo.com/)** — free, **no API key, no registration**; geocoding + forecast, with Chinese-language city resolution (administrative-city ranking to avoid village name collisions).
- Automatic fallback: **[wttr.in](https://wttr.in/)** if the primary source fails.
- WMO weather codes and wind directions are translated to Chinese in the output.
- Results cached for **600 seconds**; the hosted endpoint is rate-limited to **200 requests / minute / IP**.

## 🐢 Self-hosting

```bash
git clone https://github.com/boy-373/weather-mcp-china.git
cd weather-mcp-china
pip install -r requirements.txt
python weather_mcp_server.py
# the server listens on 127.0.0.1:8004 by default; override with:
#   MCP_HOST=0.0.0.0 MCP_PORT=9000 python weather_mcp_server.py
#   MCP_ALLOWED_HOSTS="your-domain.com,127.0.0.1:*"
#   MCP_ALLOWED_ORIGINS="https://your-domain.com"
```

Then point your MCP client at `http://127.0.0.1:8004/mcp`.
No API keys or accounts are ever required.

### 🐳 Self-host with Docker

**Option A — pull the pre-built image (fastest, no build):**

```bash
docker run -d -p 8000:8000 --name weather-mcp-china ghcr.io/boy-373/weather-mcp-china:latest
```

**Option B — build from source:**

```bash
git clone https://github.com/boy-373/weather-mcp-china.git
cd weather-mcp-china
docker build -t weather-mcp-china .
docker run -d -p 8000:8000 --name weather-mcp-china weather-mcp-china
```

Then point your MCP client at `http://127.0.0.1:8000/mcp`.
The container listens on `0.0.0.0:8000` by default (override with `-e MCP_PORT=9000` and adjust `-p` accordingly). No API keys or accounts required.




## 🗂️ Files

- `weather_mcp_server.py` — the MCP server (FastMCP, Streamable HTTP transport).
- `rate_limit.py` — lightweight per-IP sliding-window rate-limit middleware (200 req/min default).
- `requirements.txt` — `mcp`, `uvicorn`, `starlette`.
- `server.json` — official MCP Registry manifest (remote server entry, ready to publish with `mcp-publisher`).
- `smithery.yaml` / `glama.json` — directory listing metadata.

---

## 🇨🇳 中文使用说明

**一句话**：全球城市实时天气与多日预报，中文城市名直接查、结果中文输出，最长 7 天预报。

**在线直连地址（免费、无需 Key、开箱即用）**：`https://mcp.pianam.cn/weather-mcp/mcp`

在 MCP 客户端（Claude Desktop / Cursor / Cherry Studio / Cline 等）的配置里加入：

```json
{
  "mcpServers": {
    "weather": {
      "type": "http",
      "url": "https://mcp.pianam.cn/weather-mcp/mcp"
    }
  }
}
```

**工具**：

- `query_weather(city, days)`：查天气。城市名中英文均可（「青岛」「北京」「Tokyo」），`days` 为预报天数（1-7，默认 3）。
- 返回当前天气（天气状况/温度/体感温度/湿度/风向风速）+ 每日预报（日期/天气/最高最低温/降水概率）。
- 主数据源 Open-Meteo（免费无需 Key），故障自动切换 wttr.in。

**服务特性**：数据源全部为公开接口、无需注册/付费；服务端内存缓存、失败自动降级/切换备用通道；单 IP 限流 200 次/分钟。

**本地部署**：

```bash
git clone https://github.com/boy-373/weather-mcp-china.git
cd weather-mcp-china
pip install -r requirements.txt
python weather_mcp_server.py
# 默认监听 127.0.0.1:8004，可用环境变量 MCP_HOST / MCP_PORT / MCP_ALLOWED_HOSTS / MCP_ALLOWED_ORIGINS 覆盖
```


**Docker 自托管**：

```bash
# 方式一：直接拉预构建镜像（最快，无需构建）
docker run -d -p 8000:8000 --name weather-mcp-china ghcr.io/boy-373/weather-mcp-china:latest

# 方式二：从源码构建
git clone https://github.com/boy-373/weather-mcp-china.git && cd weather-mcp-china
docker build -t weather-mcp-china .
docker run -d -p 8000:8000 --name weather-mcp-china weather-mcp-china
# MCP 地址填：http://127.0.0.1:8000/mcp
```

容器默认监听 `0.0.0.0:8000`（可用 `-e MCP_PORT=端口` 改），无需任何 API Key 或账号。

## 📄 License

[MIT](LICENSE) © 2026 boy-373

## Install via Smithery

One-click install for [Smithery](https://smithery.ai)-supported clients (Claude Desktop, Cursor, etc.):

[![Smithery](https://smithery.ai/badge/1561852680/weather-mcp-china)](https://smithery.ai/servers/1561852680/weather-mcp-china)

Or run:

```bash
npx -y @smithery/cli install 1561852680/weather-mcp-china --client claude
```

---

## 🔌 Use with Any AI Client — One-Click MCP Gateway

We host a free **MCP aggregation gateway**: your AI assistant (Cherry Studio, Claude Desktop, Cursor, Cline — any MCP client) discovers and uses MCP tools through a single URL:

```
https://mcp.pianam.cn/ai/mcp
```

Add it once, then talk in plain language — the AI automatically **searches → inspects → calls** the right MCP for you.

- 🔍 Search across **22,000+** indexed MCP servers (Chinese & English)
- ⚡ **50+ live hosted MCPs** callable directly out of the box (weather, exchange rates, hot trends, IP geo, train tickets…)
- 📦 GitHub-based MCPs: search finds them with links to install locally
- ✅ Servers health-checked weekly — alive ones ranked first
- 🆓 Free to use, no key required

**📖 3-step setup guide / 中文接入教程**: https://mcp.pianam.cn/ai-gateway
