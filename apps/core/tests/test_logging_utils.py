import logging
import sys

from apps.core.logging_utils import JsonFormatter


def test_json_formatter_includes_base_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name='apps.core.test',
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg='hello %s',
        args=('world',),
        exc_info=None,
    )

    payload = formatter.format(record)

    assert '"level": "INFO"' in payload
    assert '"logger": "apps.core.test"' in payload
    assert '"message": "hello world"' in payload
    assert '"timestamp":' in payload


def test_json_formatter_includes_optional_extra_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name='apps.core.test',
        level=logging.WARNING,
        pathname=__file__,
        lineno=20,
        msg='warn',
        args=(),
        exc_info=None,
    )
    record.event = 'sync_failed'
    record.duration_ms = 123
    record.extra_data = {'step': 'login'}

    payload = formatter.format(record)

    assert '"event": "sync_failed"' in payload
    assert '"duration_ms": 123' in payload
    assert '"extra_data": {"step": "login"}' in payload


def test_json_formatter_includes_exception_trace():
    formatter = JsonFormatter()
    try:
        raise ValueError('boom')
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name='apps.core.test',
        level=logging.ERROR,
        pathname=__file__,
        lineno=30,
        msg='failed',
        args=(),
        exc_info=exc_info,
    )

    payload = formatter.format(record)

    assert '"exception":' in payload
    assert 'ValueError: boom' in payload
