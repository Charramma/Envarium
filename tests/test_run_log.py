from __future__ import annotations

from envarium.infrastructure.run_log import RunLog, RunLogKind


def test_record_command_quotes_arguments_with_spaces() -> None:
    log = RunLog()

    log.record_command(["C:/Program Files/Python/python.exe", "-m", "pip", "--version"])

    entry = log.entries()[0]
    assert entry.kind is RunLogKind.COMMAND
    assert entry.text == '"C:/Program Files/Python/python.exe" -m pip --version'


def test_subscribers_receive_entries_until_unsubscribed() -> None:
    log = RunLog()
    received = []
    log.subscribe(received.append)

    log.record_output("installing")
    log.unsubscribe(received.append)
    log.record_error("failed")

    assert [entry.text for entry in received] == ["installing"]
    assert [entry.text for entry in log.entries()] == ["installing", "failed"]


def test_clear_removes_all_entries() -> None:
    log = RunLog()
    log.record_info("hello")

    log.clear()

    assert log.entries() == []


def test_oldest_entries_are_trimmed_when_limit_reached() -> None:
    log = RunLog(max_entries=2)

    log.record_info("one")
    log.record_info("two")
    log.record_info("three")

    assert [entry.text for entry in log.entries()] == ["two", "three"]
