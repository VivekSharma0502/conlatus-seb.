import hashlib
import hmac
import logging

import sys
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from core.config import settings

log = logging.getLogger("seb")
if not log.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(levelname)s:     [%(name)s] %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)

PROTECTED_PREFIXES = ("/interview",)
PUBLIC_PREFIXES = ("/interview/details/", "/seb/")  # launch page and config download need this before SEB


def _public_url(request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "")).split(",")[0].strip()
    raw_path = request.scope.get("raw_path")
    path = raw_path.decode() if raw_path else request.url.path
    query = request.url.query
    return f"{proto}://{host}{path}" + (f"?{query}" if query else "")


class SEBMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        needs_seb = path.startswith(PROTECTED_PREFIXES) and not any(path.startswith(p) for p in PUBLIC_PREFIXES)

        if not needs_seb or request.method == "OPTIONS":
            return await call_next(request)

        # Check DEV_SKIP_SEB from settings
        if settings.DEV_SKIP_SEB:
            return await call_next(request)

        # Read SEB_CONFIG_KEY from settings
        keys = [k.strip() for k in settings.SEB_CONFIG_KEY.split(",") if k.strip()]
        if not keys:
            log.error("SEB_CONFIG_KEY not set in settings, failing closed")
            return JSONResponse({"detail": "Server SEB config missing"}, status_code=500)

        sent = request.headers.get("x-safeexambrowser-configkeyhash", "").lower()

        # Build candidate URLs:
        # (a) The request URL as now
        # (b) The Referer header without the #fragment
        req_url = _public_url(request)
        candidates: list[tuple[str, str]] = [("request_url", req_url)]

        raw_referer = request.headers.get("referer", "").strip()
        if raw_referer:
            referer_url = raw_referer.split("#")[0]
            if referer_url and referer_url != req_url:
                candidates.append(("referer", referer_url))

        # Accept if SHA256(candidate + key) matches received hash for any candidate and key
        matched_candidate: str | None = None
        for label, candidate_url in candidates:
            for k in keys:
                computed = hashlib.sha256((candidate_url + k).encode()).hexdigest()
                if sent and hmac.compare_digest(computed, sent):
                    matched_candidate = label
                    break
            if matched_candidate:
                break

        if matched_candidate:
            log.info("SEB check PASSED matched=%s", matched_candidate)
            return await call_next(request)

        log.warning("SEB check failed url=%s header_present=%s", req_url, bool(sent))
        return JSONResponse({"detail": "Safe Exam Browser required"}, status_code=403)
