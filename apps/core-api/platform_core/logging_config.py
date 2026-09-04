"""Structured Logging (JSON) — القسم 6.7.

كل سطر لوق يجب أن يحمل: request_id, tenant_id (company_id), user_id.
ممنوع استخدام print() في أي مكان بالمشروع (القسم 11.4) — فقط عبر get_logger().
"""
import logging


def configure_logging(environment: str = "development") -> None:
    level = logging.DEBUG if environment == "development" else logging.INFO
    logging.basicConfig(
        level=level,
        format='{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
