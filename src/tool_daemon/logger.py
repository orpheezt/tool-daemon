import json
import logging
import sys
import time
from dataclasses import asdict, dataclass

from rich.logging import RichHandler


@dataclass
class LogRecordPayload:
    timestamp: str
    level: str
    logger: str
    message: str
    agent_id: str | None = None
    job_id: str | None = None
    status: str | None = None
    exception: str | None = None

    def to_json(self) -> str:
        data = {k: v for k, v in asdict(self).items() if v is not None}
        return json.dumps(data)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = LogRecordPayload(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            agent_id=getattr(record, "agent_id", None),
            job_id=getattr(record, "job_id", None),
            status=getattr(record, "status", None),
        )

        if record.exc_info:
            payload.exception = self.formatException(record.exc_info)

        return payload.to_json()


def setup_logger(
    name: str = "tool.daemon",
    level: str = "INFO",
    log_format: str = "json",
    log_file: str | None = None,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    handler: logging.Handler
    if log_file:
        formatter = (
            JsonFormatter()
            if log_format.lower() == "json"
            else logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
            )
        )
        handler = logging.FileHandler(log_file)
        handler.setFormatter(formatter)
    else:
        match log_format.lower():
            case "text":
                handler = RichHandler(
                    rich_tracebacks=True,
                    show_time=True,
                    show_level=True,
                    show_path=False,
                )
            case _:
                handler = logging.StreamHandler(sys.stdout)
                handler.setFormatter(JsonFormatter())

    logger.addHandler(handler)
    return logger
