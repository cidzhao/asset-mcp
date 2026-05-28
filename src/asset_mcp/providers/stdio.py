from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout


@contextmanager
def redirect_sdk_stdout() -> Iterator[None]:
    # MCP stdio uses stdout for JSON-RPC frames only. Broker/exchange SDKs can
    # print banners, permission tables, or native logs to fd 1, which corrupts
    # the protocol and shows up as "Transport closed" in clients.
    #
    # Wrap third-party SDK calls with this helper when adding a provider. This
    # redirects both Python sys.stdout and low-level fd 1 writes to stderr.
    saved_stdout_fd = os.dup(1)
    try:
        sys.stdout.flush()
        os.dup2(2, 1)
        with redirect_stdout(sys.stderr):
            yield
    finally:
        sys.stdout.flush()
        os.dup2(saved_stdout_fd, 1)
        os.close(saved_stdout_fd)
