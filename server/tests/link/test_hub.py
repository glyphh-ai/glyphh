"""The hub: who is connected and who is watching, in this process."""

import uuid

from glyphh_server.link.hub import WAITING, Hub


async def test_a_newer_connection_is_not_forgotten_when_an_older_one_goes() -> None:
    hub, mac = Hub(), uuid.uuid4()
    sent: list[str] = []

    async def old(text: str) -> None:
        sent.append(f"old {text}")

    async def new(text: str) -> None:
        sent.append(f"new {text}")

    hub.connected(mac, old)
    hub.connected(mac, new)
    hub.gone(mac, old)
    assert hub.online(mac) and await hub.tell(mac, {"a": 1}) and sent == ['new {"a": 1}']
    hub.gone(mac, new)
    assert not await hub.tell(mac, {"a": 1})


async def test_a_watcher_too_far_behind_misses_events_and_ending_wakes_every_watcher() -> None:
    hub, thread = Hub(), uuid.uuid4()
    async with hub.watch(thread) as queue:
        for i in range(WAITING + 5):
            hub.publish(thread, {"seq": i})
        assert queue.qsize() == WAITING
        hub.end(thread)
    hub.publish(thread, {"seq": 0})
