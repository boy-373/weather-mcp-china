# -*- coding: utf-8 -*-
"""
轻量限流中间件（自营 MCP 共用，2026-09-01）
------------------------------------------
按真实客户端 IP 对 POST 请求做每分钟配额限制，超限返回 HTTP 429。
纯内存滑窗实现，单进程足够；服务重启计数清零。
部署：与各 MCP server 脚本放同一目录，脚本中：
    from rate_limit import RateLimitMiddleware
    _app = mcp.streamable_http_app()
    _app.add_middleware(RateLimitMiddleware, limit_per_minute=60)
"""
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


def client_ip(request):
    """nginx 反代后取真实访客 IP：X-Forwarded-For 第一个 -> X-Real-IP -> 直连地址。"""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    xri = request.headers.get("x-real-ip", "")
    if xri.strip():
        return xri.strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_minute: int = 60):
        super().__init__(app)
        self.limit = int(limit_per_minute)
        self._hits = defaultdict(deque)

    async def dispatch(self, request, call_next):
        if request.method == "POST":
            ip = client_ip(request)
            now = time.time()
            q = self._hits[ip]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.limit:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32000,
                            "message": "请求过于频繁，请约 1 分钟后再试（单 IP 每分钟限 %d 次）" % self.limit,
                        },
                    },
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            q.append(now)
            # 控制内存：清理超过 1000 个 IP 且队列为空的条目
            if len(self._hits) > 1000:
                for k in [k for k, v in self._hits.items() if not v]:
                    self._hits.pop(k, None)
        return await call_next(request)
