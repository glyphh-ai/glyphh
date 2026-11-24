"""The timing check on headers written for the purpose (screener/timing.py). These are crafted cases: they show
the code measures and names what it was built to; they say nothing about how real senders' timestamps look."""

from datetime import UTC, datetime

from screener import mail, timing

DATE: str = "Tue, 24 Nov 2026 09:15:00 -0600"  # 15:15:00 UTC


def hop(at: str, by: str = "mx.example") -> str:
    return f"from out.example by {by} with ESMTPS id abc; {at}"


CLEAN: list[str] = [hop("Tue, 24 Nov 2026 15:15:09 +0000", "inbox.example"), hop("Tue, 24 Nov 2026 15:15:04 +0000")]


def test_an_ordinary_email_raises_nothing() -> None:
    got = timing.read(DATE, CLEAN, datetime(2026, 11, 24, 16, 0, tzinfo=UTC))
    assert got["flags"] == ["none"] and timing.found(got) == []
    assert (got["hops"], got["order"], got["first_gap"], got["longest_gap"], got["total"]) == (2, "in_order", 4, 5, 9)
    assert (got["local_hour"], got["zone"], got["dated"]) == (9, "-0600", "yes")
    assert got["arrived"] == "2026-11-24T15:15:09+00:00" and len(got["windows"]) == 2


def test_a_date_after_the_first_server_had_it_and_a_date_after_now() -> None:
    ahead = timing.read("Tue, 24 Nov 2026 10:15:00 -0600", CLEAN)
    assert ahead["flags"] == ["future_date"] and ahead["first_gap"] == timing.GAP_MIN
    assert timing.read(DATE, CLEAN[1:], datetime(2026, 11, 24, 15, 0, tzinfo=UTC))["flags"] == ["future_date"]
    assert timing.read(DATE, CLEAN[1:], datetime(2026, 11, 24, 15, 14, tzinfo=UTC))["flags"] == ["none"]  # skew


def test_servers_out_of_order_and_a_long_wait_between_them() -> None:
    back = timing.read(DATE, [hop("Tue, 24 Nov 2026 15:05:00 +0000"), hop("Tue, 24 Nov 2026 15:15:04 +0000")])
    assert back["order"] == "out_of_order" and "out_of_order" in back["flags"]
    slow = timing.read(DATE, [hop("Tue, 24 Nov 2026 17:30:00 +0000"), hop("Tue, 24 Nov 2026 15:15:04 +0000")])
    assert slow["flags"] == ["long_gap"] and slow["longest_gap"] == timing.WAIT_MAX
    assert "more than an hour between two servers" in timing.found(slow)[0]


def test_an_email_dated_long_before_it_was_sent_and_one_sent_at_an_odd_hour() -> None:
    held = timing.read("Tue, 24 Nov 2026 06:00:00 -0600", CLEAN)
    assert held["flags"] == ["held_back"] and held["first_gap"] == timing.GAP_MAX
    night = timing.read("Tue, 24 Nov 2026 03:10:00 +0100", [hop("Tue, 24 Nov 2026 02:10:05 +0000")])
    assert night["flags"] == ["odd_hour"] and night["local_hour"] == 3
    assert timing.read("Tue, 24 Nov 2026 05:00:00 +0100", [hop("Tue, 24 Nov 2026 04:00:05 +0000")])["flags"] == ["none"]


def test_what_cannot_be_read_is_said_and_left_out() -> None:
    bare = timing.read("", [])
    assert bare["flags"] == ["no_date", "no_hops"] and "first_gap" not in bare and "local_hour" not in bare
    assert (bare["dated"], bare["hops"], bare["order"], bare["windows"]) == ("no", 0, "none", [])
    dated = timing.read(DATE, ["from a by b with SMTP", hop("not a time")])
    assert dated["flags"] == ["no_hops"] and dated["hops"] == 0 and len(dated["windows"]) == 2
    assert timing.stamp("24 Nov 2026 15:15:00").tzinfo is UTC  # type: ignore[union-attr]


def test_messages_within_five_minutes_share_a_window_and_a_burst_is_named() -> None:
    at = datetime(2026, 11, 24, 15, 19, 50, tzinfo=UTC)
    near, far = datetime(2026, 11, 24, 15, 20, 10, tzinfo=UTC), datetime(2026, 11, 24, 15, 45, tzinfo=UTC)
    assert set(timing.windows(at)) & set(timing.windows(near)) and not set(timing.windows(at)) & set(timing.windows(far))
    got = timing.read(DATE, CLEAN)
    assert timing.with_burst(got, 2)["flags"] == ["none"]
    burst = timing.with_burst(got, 4)
    assert burst["flags"] == ["burst"] and timing.found(burst) == ["4 other applications arrived within ten minutes of it"]


def test_a_message_is_read_with_every_received_header_and_a_paste_with_or_without_headers() -> None:
    raw = (f"Received: {CLEAN[0]}\r\nReceived: {CLEAN[1]}\r\nFrom: Ann Lee <ann@b.example>\r\nDate: {DATE}\r\n"
           "Subject: Data Analyst\r\n\r\nHello there.\r\n").encode()  # fmt: skip
    got = mail.read(raw)
    assert got.received == CLEAN and got.date == DATE and got.text.strip() == "Hello there."
    source = mail.pasted(raw.decode(), [("cv.pdf", b"%PDF-1.4 x"), ("notes.xyz", b"??")])
    assert source.headers["from"] == "Ann Lee <ann@b.example>" and [f[:2] for f in source.files] == [("cv.pdf", "pdf")]
    words = mail.pasted("Hello,\nI would like to apply.", [])
    assert words.headers == {} and words.received == [] and words.text.startswith("Hello,")
