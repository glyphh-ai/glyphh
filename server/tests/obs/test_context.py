from glyphh_server.obs import context
from glyphh_server.obs.context import accept_trace_id, bound, current_trace_id, new_trace_id


def test_a_callers_trace_id_is_kept_only_when_it_is_a_safe_shape() -> None:
    assert accept_trace_id("req-12345678") == "req-12345678"
    for unsafe in (None, "", "short", "has spaces in it", "x" * 65, "semi;colon-1234"):
        replaced = accept_trace_id(unsafe)
        assert replaced != unsafe and len(replaced) == 32


def test_new_trace_ids_are_unique() -> None:
    assert new_trace_id() != new_trace_id()


def test_current_trace_id_makes_one_when_none_is_set_and_keeps_it() -> None:
    with bound(trace="outer-trace-1"):
        assert current_trace_id() == "outer-trace-1"
    token = context.trace_id.set(None)
    try:
        made = current_trace_id()
        assert made == current_trace_id() == context.trace_id.get()
    finally:
        context.trace_id.reset(token)


def test_bound_sets_the_context_for_the_block_and_restores_it_after() -> None:
    with bound(trace="trace-aaaaaaaa", user="u1", org="o1"):
        assert (context.trace_id.get(), context.user_id.get(), context.org_id.get()) == ("trace-aaaaaaaa", "u1", "o1")
        with bound(user="u2"):
            assert (context.trace_id.get(), context.user_id.get()) == ("trace-aaaaaaaa", "u2")
        assert context.user_id.get() == "u1"
    assert context.user_id.get() is None and context.org_id.get() is None


def test_bound_restores_even_when_the_block_raises() -> None:
    try:
        with bound(user="u9"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert context.user_id.get() is None
