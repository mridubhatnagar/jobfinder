import logging
import sys

MAX_LINE = 300


def _truncate(s, limit=MAX_LINE):
    if not isinstance(s, str) or len(s) <= limit:
        return s
    return s[: limit - 3] + "..."


def _scrub_exception(exc):
    # raise ValueError(f"...{jd_text}") puts JD content in exc.args, which
    # Python's default printer renders straight into stderr — and into public
    # GH Actions logs for this repo. Walk the chain and truncate.
    if exc is None:
        return
    try:
        exc.args = tuple(_truncate(a) for a in exc.args)
    except Exception:
        pass
    _scrub_exception(exc.__cause__)
    if exc.__context__ is not exc.__cause__:
        _scrub_exception(exc.__context__)


class SafeFormatter(logging.Formatter):
    def formatMessage(self, record):
        record.message = _truncate(record.message)
        return super().formatMessage(record)

    def formatException(self, exc_info):
        rendered = super().formatException(exc_info)
        return "\n".join(_truncate(line) for line in rendered.splitlines())


def _excepthook(exc_type, exc_value, exc_traceback):
    _scrub_exception(exc_value)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def setup_logging(level=logging.INFO):
    handler = logging.StreamHandler(sys.stdout)
    formatter = SafeFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.addHandler(handler)

    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("google_auth_httplib2").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.INFO)

    sys.excepthook = _excepthook

    return logging.getLogger("jobfinder")
