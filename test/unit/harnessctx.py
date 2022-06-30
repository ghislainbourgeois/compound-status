import typing
from typing import Type, Protocol, Callable

from ops.charm import CharmBase, CharmEvents
from ops.framework import EventSource, BoundEvent, Handle, EventBase, Framework
from ops.testing import Harness


class _HasOn(Protocol):
    @property
    def on(self) -> CharmEvents:
        ...


def _DefaultEmitter(charm: CharmBase, harness: Harness):
    return charm


class Emitter:
    def __init__(self, harness: Harness, emit: Callable[[], EventBase]):
        self.harness = harness
        self._emit = emit
        self.event = None
        self._emitted = False

    @property
    def emitted(self):
        return self._emitted

    def emit(self):
        assert not self._emitted, "already emitted; should not emit twice"
        self.event = self._emit()
        self._emitted = True
        return self.event


class HarnessCtx:
    """

    Usage:

    """

    def __init__(
        self,
        charm: Type[CharmBase],
        event_name: str,
        emitter: Callable[[CharmBase, Harness], _HasOn] = _DefaultEmitter,
        *args,
        **kwargs
    ):
        self.charm_cls = charm
        self.emitter = emitter
        self.event_name = event_name.replace("-", "_")
        self.event_args = args
        self.event_kwargs = kwargs

    def __enter__(self):
        self._harness = harness = Harness(self.charm_cls)
        harness.begin()

        emitter = self.emitter(harness.charm, harness)
        events = getattr(emitter, "on")
        event_source: BoundEvent = getattr(events, self.event_name)

        def _emit():
            # we don't call event_source.emit()
            # because we want to grab the event
            framework = event_source.emitter.framework
            key = framework._next_event_key()
            handle = Handle(event_source.emitter, event_source.event_kind, key)
            event = event_source.event_type(
                handle, *self.event_args, **self.event_kwargs
            )
            event.framework = framework
            framework._emit(event)
            return event

        self._emitter = bound_ctx = Emitter(harness, _emit)
        return bound_ctx

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._emitter.emitted:
            self._emitter.emit()
        self._harness.framework.on.commit.emit()