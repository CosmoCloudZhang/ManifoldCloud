"""Set up command-line logging and remove credentials from log records."""

import http.client
import json
import logging
import re


_QUOTED_HEADER = re.compile(
    r"(?P<label>['\"](?:authorization|x-token)['\"]\s*:\s*)"
    r"(?P<quote>['\"])(?:\\.|(?!(?P=quote))[^\\])*(?P=quote)",
    re.IGNORECASE,
)
_HEADER_LINE = re.compile(r"(\b(?:authorization|x-token)\s*[:=])[^\r\n]*", re.IGNORECASE)
_HTTP_LOGGERS = ("requests", "urllib3", "http.client", "aiohttp", "fsspec.http")


class RedactionFilter(logging.Filter):
    """Sanitise rendered messages, traceback text and stack text before output."""

    def __init__(self, secrets=()):
        super().__init__()
        forms = set()
        for secret in filter(None, secrets):
            forms.update((secret, repr(secret)[1:-1], json.dumps(secret)[1:-1]))
        self.secrets = tuple(sorted(forms, key=len, reverse=True))

    def redact(self, message):
        message = _QUOTED_HEADER.sub(r"\g<label>\g<quote>[REDACTED]\g<quote>", message)
        message = _HEADER_LINE.sub(r"\1 [REDACTED]", message)
        for secret in self.secrets:
            message = message.replace(secret, "[REDACTED]")
        return message

    def filter(self, record):
        if record.levelno <= logging.DEBUG and any(
            record.name == name or record.name.startswith(name + ".") for name in _HTTP_LOGGERS
        ):
            return False

        record.msg, record.args = self.redact(record.getMessage()), ()
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = self.redact(record.exc_text)
            record.exc_info = None
        if record.stack_info:
            record.stack_info = self.redact(record.stack_info)
        return True


def setup_logging(*, level=logging.INFO, secrets=(), stream=None):
    """Configure console logging and apply redaction to the existing root handlers."""
    http.client.HTTPConnection.debuglevel = 0
    http.client.HTTPSConnection.debuglevel = 0
    for name in _HTTP_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.basicConfig(level=level, format="%(levelname)s %(message)s", stream=stream)
    redaction = RedactionFilter(secrets)
    for handler in logging.getLogger().handlers:
        handler.addFilter(redaction)
    return redaction
