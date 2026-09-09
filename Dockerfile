# weather-mcp-china — 中文 MCP Server（自托管镜像）
# 基于 Python 3.12 slim，开箱即用，无需 API Key
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

WORKDIR /app

# 先装依赖（利用层缓存）
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 再拷代码
COPY . .

EXPOSE 8000

# FastMCP streamable-http，默认监听 0.0.0.0:8000，MCP 路径 /mcp
CMD ["python", "weather_mcp_server.py"]
