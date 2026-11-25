"""Check that authentication details stay out of console logging."""

import io
import logging
import unittest

from manifoldcloud.logs import RedactionFilter


class LoggingTests(unittest.TestCase):
    def setUp(self):
        self.password = "fake-passw0rd"
        self.token = "fake-bearer-token"
        self.output = io.StringIO()
        self.handler = logging.StreamHandler(self.output)
        self.handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        self.handler.addFilter(RedactionFilter((self.password, self.token)))
        self.logger = logging.Logger("manifoldcloud.test", level=logging.DEBUG)
        self.logger.addHandler(self.handler)
        self.addCleanup(self.handler.close)

    def test_known_secrets_and_headers_are_removed_at_every_level(self):
        for level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL):
            self.logger.log(level, "Password %s and token %s", self.password, self.token)
        self.logger.warning("headers=%r", {"AUTHORIZATION": "Basic unknown-secret", "X-Token": "new-token"})
        self.logger.warning("authorization: Token raw-token\nx-token=another-token")

        output = self.output.getvalue()
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            self.assertIn(f"{level} Password [REDACTED] and token [REDACTED]", output)
        self.assertNotIn(self.password, output)
        self.assertNotIn(self.token, output)
        self.assertNotIn("unknown-secret", output)
        self.assertNotIn("new-token", output)
        self.assertNotIn("raw-token", output)
        self.assertNotIn("another-token", output)

    def test_exception_text_is_redacted(self):
        try:
            raise RuntimeError(f"Unexpected {self.password}; X-Token: unregistered-token")
        except RuntimeError:
            self.logger.exception("Exchange failed")

        output = self.output.getvalue()
        self.assertIn("Traceback (most recent call last)", output)
        self.assertIn("RuntimeError: Unexpected [REDACTED]; X-Token: [REDACTED]", output)
        self.assertNotIn(self.password, output)
        self.assertNotIn("unregistered-token", output)

    def test_http_debug_record_is_suppressed(self):
        http_logger = logging.Logger("urllib3.connectionpool", level=logging.DEBUG)
        http_logger.addHandler(self.handler)
        http_logger.debug("Request details")
        http_logger.warning("Connection closed")
        self.assertEqual(self.output.getvalue(), "WARNING Connection closed\n")

    def test_escaped_secret_is_redacted(self):
        password = "path\\with\nwhitespace"
        redaction = RedactionFilter((password,))
        self.assertEqual(redaction.redact(f"Password {password!r}"), "Password '[REDACTED]'")
