import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response, HTTPException
from app.core.redis import redis_client

class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = 100, window: int = 60):
        super().__init__(app)
        self.limit = limit
        self.window = window

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"
        
        redis = await redis_client.get_client()
        
        # Simple fixed window counter
        try:
            count = await redis.get(key)
            if count and int(count) >= self.limit:
                return Response(
                    content="Too many requests",
                    status_code=429
                )
            
            pipe = redis.pipeline()
            await pipe.incr(key)
            await pipe.expire(key, self.window)
            await pipe.execute()
            
        except Exception:
            # Fallback if Redis is down
            pass

        response = await call_next(request)
        return response
