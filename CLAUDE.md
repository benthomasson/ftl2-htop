# CLAUDE.md

## What This Is

This is a reference example of building an application on top of FTL2's gate event protocol. It demonstrates the key patterns for using FTL2 as a library rather than as a configuration management tool.

## FTL2 Patterns Demonstrated

### 1. PEP 723 Inline Script Metadata

```python
# /// script
# dependencies = ["ftl2 @ git+https://github.com/benthomasson/ftl2", "rich"]
# requires-python = ">=3.13"
# ///
```

FTL2 apps can be single-file scripts runnable with `uv run` or packaged with `pyproject.toml` for `uvx`. No virtual environment setup needed.

### 2. Gate Subsystem Initialization

```python
async with automation(inventory=args.inventory, gate_subsystem=True) as ftl:
```

`gate_subsystem=True` tells FTL2 to start persistent gate processes on remote hosts via SSH subsystem. The gate stays running for the lifetime of the `async with` block, enabling bidirectional communication.

### 3. Host Group Iteration

```python
groups = list(ftl.hosts.groups)
for group in groups:
    proxy = getattr(ftl, group)
```

`ftl.hosts.groups` returns all groups from the inventory. `getattr(ftl, group)` returns a `HostScopedProxy` that targets all hosts in that group. You can also target individual hosts: `ftl.webserver` for a host named `webserver`.

### 4. Gate Commands (Request/Response)

```python
await proxy.monitor(interval=2.0, include_processes=True)
```

This sends a `StartMonitor` command to the gate process on the remote host and waits for a `MonitorResult` response. The proxy method wraps `_send_gate_command()` which handles the JSON message protocol over the SSH channel.

### 5. Event Registration

```python
proxy.on("SystemMetrics", lambda m: metrics_store.update({m.get("hostname"): m}))
```

`proxy.on(event_type, handler)` registers a callback for unsolicited events from the gate. The handler receives the event data dict. Handlers can be sync or async. Multiple handlers can be registered for the same event type.

### 6. Event Listening

```python
await ftl.listen()
```

`ftl.listen()` blocks and dispatches events from all active gate connections. It runs one coroutine per gate via `asyncio.gather`. Events are dispatched to handlers registered with `proxy.on()`.

### 7. Concurrent Listen + Application Logic

```python
await asyncio.gather(
    ftl.listen(),
    update_display(),
)
```

`ftl.listen()` runs alongside application logic. Here the TUI display updates on a 0.5s timer while `listen()` dispatches incoming metrics events to the handler that populates `metrics_store`.

### 8. System Package Dependencies

psutil has C extensions and can't be bundled in the gate .pyz. Instead, install it on the remote host using FTL2's normal module system before enabling monitoring:

```python
await ftl.webservers.dnf(name="python3-psutil", state="present")
```

Rule: pure-Python deps go in the gate .pyz bundle; compiled deps get installed on the host via dnf/apt.

## Event Protocol Summary

The gate communicates via JSON tuples over length-prefixed messages on the SSH channel:

- **Request/Response**: Controller sends `["StartMonitor", {interval: 2}]`, gate replies `["MonitorResult", {status: "ok"}]`
- **Unsolicited Events**: Gate sends `["SystemMetrics", {cpu: ..., memory: ..., ...}]` every interval
- Events can arrive interleaved with command responses — the protocol handles this transparently

## Running

```bash
# Via uvx (no clone needed)
uvx --from "git+https://github.com/benthomasson/ftl2-htop" ftl2-htop -i inventory.yml

# From source
uv run ftl2_htop.py -i inventory.yml

# Debug mode (raw events, no TUI)
ftl2-htop -i inventory.yml --debug
```

## Key Files

- `ftl2_htop.py` — the entire application (single file)
- `pyproject.toml` — package metadata and `ftl2-htop` console script entry point
- `inventory.example.yml` — example Ansible-style inventory

## Related FTL2 Source

- `src/ftl2/automation/__init__.py` — `automation()` context manager
- `src/ftl2/automation/proxy.py` — `HostScopedProxy` with `monitor()`, `on()`, `watch()`
- `src/ftl2/automation/context.py` — `AutomationContext` with `listen()`, event dispatch
- `src/ftl2/ftl_gate/__main__.py` — `SystemMonitor` class in the gate process
- `src/ftl2/message.py` — message types and event protocol
