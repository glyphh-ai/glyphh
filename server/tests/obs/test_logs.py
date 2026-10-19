import json
import logging

import pytest

from glyphh_server.obs.context import bound
from glyphh_server.obs.logs import JsonFormatter, configure, fields


def _record(msg: str, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("glyphh.test", logging.WARNING, __file__, 1, msg, None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_a_line_is_json_with_its_trace_user_org_and_fields() -> None:
    with bound(trace="trace-12345678", user="u1", org="o1"):
        line = json.loads(JsonFormatter().format(_record("hello", **fields(path="/v1/me", n=2))))
    assert line["message"] == "hello" and line["level"] == "warning" and line["logger"] == "glyphh.test"
    assert (line["trace_id"], line["user_id"], line["org_id"]) == ("trace-12345678", "u1", "o1")
    assert (line["path"], line["n"]) == ("/v1/me", 2)
    assert "error" not in line


def test_a_line_carries_the_traceback_of_its_exception() -> None:
    try:
        raise ValueError("bad value")
    except ValueError:
        import sys

        record = logging.LogRecord("glyphh.test", logging.ERROR, __file__, 1, "crashed", None, sys.exc_info())
    line = json.loads(JsonFormatter().format(record))
    assert "ValueError: bad value" in line["error"]


def test_fields_that_are_not_a_mapping_are_ignored() -> None:
    line = json.loads(JsonFormatter().format(_record("x", fields="not a dict")))
    assert line["message"] == "x" and "fields" not in line


def test_configure_installs_one_json_handler_however_often_it_runs(capsys: pytest.CaptureFixture[str]) -> None:
    configure("debug")
    configure("info")
    root = logging.getLogger()
    assert [h.get_name() for h in root.handlers].count("glyphh-json") == 1
    assert root.level == logging.INFO
    logging.getLogger("glyphh.test").info("written", extra=fields(k="v"))
    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(out)["k"] == "v"


def test_the_access_line_of_a_heartbeat_or_otlp_batch_is_dropped_so_no_address_is_logged() -> None:
    from glyphh_server.obs.logs import NoAddress

    def access(path: object) -> logging.LogRecord:
        args = ("203.0.113.9:5555", "POST", path, "1.1", 200)
        return logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d', args, None)

    quiet = NoAddress()
    assert not quiet.filter(access("/v1/license/verify")) and not quiet.filter(access("/v1/license/verify?x=1"))
    assert not any(quiet.filter(access(f"/v1/otlp/v1/{signal}")) for signal in ("logs", "metrics", "traces"))
    assert quiet.filter(access("/v1/license")) and quiet.filter(_record("no args"))
    configure("INFO")
    configure("INFO")
    assert sum(isinstance(f, NoAddress) for f in logging.getLogger("uvicorn.access").filters) == 1
