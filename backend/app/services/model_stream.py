"""Request-local delivery of provider deltas, without changing business validation."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic

import httpx

DeltaSink = Callable[[str], None]
_sink: ContextVar[DeltaSink | None] = ContextVar("model_delta_sink", default=None)


def delta_sink() -> DeltaSink | None:
    return _sink.get()


@contextmanager
def stream_deltas(sink: DeltaSink) -> Iterator[None]:
    token = _sink.set(sink)
    try:
        yield
    finally:
        _sink.reset(token)


def bounded_lines(response: httpx.Response, deadline: float) -> Iterator[str]:
    """Limit bytes before buffering a possibly unterminated provider event."""
    size = 0
    pending = b""
    for chunk in response.iter_bytes():
        size += len(chunk)
        # SSE repeats its JSON envelope per token; allow that protocol overhead.
        if size > 1000000 or monotonic() > deadline:
            raise ValueError("response size or time exceeded")
        pending += chunk
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            if len(line) > 200000:
                raise ValueError("stream event too large")
            yield line.rstrip(b"\r").decode("utf-8")
        if len(pending) > 200000:
            raise ValueError("stream event too large")
    if pending:
        yield pending.rstrip(b"\r").decode("utf-8")
