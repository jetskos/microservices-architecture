import logging
import time


logger = logging.getLogger("soc.audit")


class SOCAuditMiddleware:
    """
    Middleware SOC:
    - Tag [SECURITY] pour accès refusés (401/403)
    - Tag [ERROR] pour erreurs serveur (>=500) et exceptions
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        try:
            response = self.get_response(request)
        except Exception as exc:  # noqa: BLE001
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            logger.exception(
                "[ERROR] unhandled_exception method=%s path=%s duration_ms=%s detail=%s",
                request.method,
                request.path,
                duration_ms,
                str(exc),
                extra={"soc_tag": "ERROR"},
            )
            raise

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        if response.status_code in (401, 403):
            logger.warning(
                "[SECURITY] access_denied method=%s path=%s status=%s duration_ms=%s remote=%s",
                request.method,
                request.path,
                response.status_code,
                duration_ms,
                request.META.get("REMOTE_ADDR", "unknown"),
                extra={"soc_tag": "SECURITY"},
            )
        elif response.status_code >= 500:
            logger.error(
                "[ERROR] server_error method=%s path=%s status=%s duration_ms=%s",
                request.method,
                request.path,
                response.status_code,
                duration_ms,
                extra={"soc_tag": "ERROR"},
            )

        return response
