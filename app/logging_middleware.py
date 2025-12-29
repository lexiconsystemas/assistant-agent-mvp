import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        request_id = str(uuid.uuid4())

        # session_id can come from header OR generated later in /chat
        session_id = request.headers.get("x-session-id")

        request.state.request_id = request_id
        request.state.session_id = session_id

        print(f"[START] request_id={request_id} session_id={session_id} {request.method} {request.url.path}")

        try:
            response = await call_next(request)
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            print(f"[ERROR] request_id={request_id} session_id={session_id} duration_ms={duration_ms} err={repr(e)}")
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)
        print(f"[END]   request_id={request_id} session_id={session_id} status={response.status_code} duration_ms={duration_ms}")

        # Return IDs to client for traceability
        response.headers["x-request-id"] = request_id
        if session_id:
            response.headers["x-session-id"] = session_id

        return response
