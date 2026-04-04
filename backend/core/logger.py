import logging.handlers
import json
import os
from datetime import datetime
from contextvars import ContextVar

# Context variable for request-id tracing
request_id_var: ContextVar[str] = ContextVar("request_id", default="no-request")

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3],
            "level": record.levelname,
            "name": record.name,
            "request_id": request_id_var.get(),
            "message": record.msg
        }
        
        # If msg is a string that looks like JSON (from our _log method), parse it
        if isinstance(record.msg, str):
            try:
                msg_data = json.loads(record.msg)
                if isinstance(msg_data, dict):
                    log_record.update(msg_data)
                    log_record.pop("message")
            except:
                log_record["message"] = {"text": record.msg}
        elif isinstance(record.msg, dict):
            log_record.update(record.msg)
            log_record.pop("message")

        return json.dumps(log_record)

class StructuredLogger:
    def __init__(self, name="grc-command-center"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            formatter = JSONFormatter()

            # Console Handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            
            # File Handler (Rotating)
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            file_handler = logging.handlers.RotatingFileHandler(
                os.path.join(log_dir, "system.log"),
                maxBytes=10*1024*1024, # 10MB
                backupCount=5
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def _get_formatter(self):
        return JSONFormatter()

    def _log(self, level, msg, **kwargs):
        log_data = {
            "text": msg,
            **kwargs
        }
        # JSON dump the message part for the formatter
        formatted_msg = json.dumps(log_data)
        self.logger.log(level, formatted_msg)

    def info(self, msg, **kwargs):
        self._log(logging.INFO, msg, **kwargs)

    def error(self, msg, **kwargs):
        self._log(logging.ERROR, msg, **kwargs)

    def warn(self, msg, **kwargs):
        self._log(logging.WARNING, msg, **kwargs)

logger = StructuredLogger()
