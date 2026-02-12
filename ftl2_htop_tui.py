"""Textual TUI for ftl2-htop.

Provides a full-screen Textual app that renders the same dashboard as the
rich.live.Live version, but compatible with textual-serve for web access.
Launched via --tui flag.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Static

from ftl2_htop import (
    metrics_store,
    render_dashboard,
)


class HtopApp(App):
    """Full-screen Textual TUI for ftl2-htop."""

    TITLE = "ftl2-htop"
    CSS = """
    #dashboard {
        height: 1fr;
        overflow-y: auto;
    }
    #status-bar {
        height: 1;
        dock: bottom;
        background: $primary-background;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit_app", "Quit", show=True),
    ]

    def __init__(self, args):
        super().__init__()
        self._args = args
        self._start_time = time.monotonic()
        self._finished = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Waiting for metrics...", id="dashboard")
        yield Static("Starting...", id="status-bar")

    def on_mount(self) -> None:
        self.set_interval(0.5, self._refresh_dashboard)
        self.set_interval(1.0, self._update_status)
        self._run_worker()

    @property
    def _elapsed(self) -> str:
        seconds = int(time.monotonic() - self._start_time)
        if seconds < 60:
            return f"{seconds}s"
        minutes, secs = divmod(seconds, 60)
        return f"{minutes}m{secs:02d}s"

    def _refresh_dashboard(self) -> None:
        """Re-render the dashboard from current metrics."""
        dashboard = self.query_one("#dashboard", Static)
        dashboard.update(render_dashboard())

    def _update_status(self) -> None:
        """Refresh the status bar."""
        status = self.query_one("#status-bar", Static)
        host_count = len(metrics_store)
        if self._finished:
            status.update(f"{host_count} host(s) | Done | {self._elapsed}")
        else:
            status.update(f"{host_count} host(s) | {self._elapsed}")

    def _run_worker(self) -> None:
        """Launch the FTL2 automation listener in a worker thread."""

        async def _async_runner():
            from ftl2 import automation
            from ftl2_htop import _record_history

            args = self._args
            automation_kwargs = {"gate_subsystem": True}
            if args.hosts:
                automation_kwargs["inventory"] = {
                    "all": {"hosts": {h: {} for h in args.hosts}}
                }
            elif args.inventory:
                automation_kwargs["inventory"] = args.inventory
            elif args.state:
                automation_kwargs["state_file"] = args.state
            else:
                automation_kwargs["inventory"] = "localhost,"

            async with automation(**automation_kwargs) as ftl:
                if args.groups:
                    groups = args.groups
                else:
                    groups = list(ftl.hosts.groups)

                if not groups:
                    self.call_from_thread(
                        self._set_status, "No groups found in inventory"
                    )
                    return

                for group in groups:
                    proxy = ftl[group]
                    await proxy.monitor(
                        interval=args.interval,
                        include_processes=not args.no_processes,
                    )

                    def _on_metrics(m, g=group):
                        host = m.get("hostname", g)
                        metrics_store[host] = m
                        _record_history(host, m)

                    proxy.on("SystemMetrics", _on_metrics)

                await ftl.listen()

        def _thread_target():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_async_runner())
                loop.close()
                self._finished = True
            except Exception as e:
                self._finished = True
                self.call_from_thread(self._set_status, f"Error: {e}")

        t = threading.Thread(target=_thread_target, daemon=True)
        t.start()

    def _set_status(self, text: str) -> None:
        status = self.query_one("#status-bar", Static)
        status.update(text)

    def action_quit_app(self) -> None:
        self.exit()


def run_tui(args) -> None:
    """Entry point for TUI mode."""
    app = HtopApp(args)
    app.run()
