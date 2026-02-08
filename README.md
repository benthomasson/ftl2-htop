# ftl2-htop

A distributed system monitor TUI built on [FTL2](https://github.com/benthomasson/ftl2). Streams live CPU, memory, disk, network, and process metrics from remote hosts via FTL2's gate event protocol, rendered as a terminal dashboard using [rich](https://github.com/Textualize/rich).

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- `python3-psutil` installed on remote hosts:

```bash
# Fedora/RHEL
dnf install python3-psutil

# Debian/Ubuntu
apt install python3-psutil
```

Or install it via FTL2 before monitoring:

```python
await ftl.webservers.dnf(name="python3-psutil", state="present")
```

## Usage

```bash
# Monitor all hosts in inventory
uv run ftl2_htop.py -i inventory.yml

# Monitor specific groups
uv run ftl2_htop.py -i inventory.yml -g webservers databases

# Faster sampling (1 second)
uv run ftl2_htop.py -i inventory.yml --interval 1

# Skip process list (less bandwidth)
uv run ftl2_htop.py -i inventory.yml --no-processes

# Debug mode — print raw events, no TUI
uv run ftl2_htop.py -i inventory.yml --debug
```

## How It Works

1. FTL2 connects to each host via SSH and starts a gate process
2. The gate's `SystemMonitor` collects metrics via psutil at the configured interval
3. Metrics are streamed back as `SystemMetrics` events over the SSH channel
4. The TUI renders live-updating panels for each host using `rich.live.Live`

```
┌──────────── web-01 ────────────┐
│ CPU  ████████░░░░░░░░░░░░  38.2%  4 cores  load: 0.52 0.71 0.80 │
│ Mem  ██████████████░░░░░░  68.3% (5.5GB/8.0GB)                   │
│ Swap ░░░░░░░░░░░░░░░░░░░░   0.0% (0B/2.0GB)                     │
│ Disk ██████████░░░░░░░░░░  50.0% (50.0GB/100.0GB)                │
│ Net  ▲ 12.1KB/s  ▼ 74.8KB/s                                     │
│ Up   10d 0h 0m                                                   │
│                                                                   │
│    PID User       CPU%      RSS Status   Name                    │
│   5678 root       45.0  500.0MB running  python3                 │
│   1234 www-data    2.1  150.0MB sleeping nginx                   │
└───────────────────────────────────────────────────────────────────┘
```

## Inventory

Create an Ansible-style inventory file:

```yaml
all:
  hosts:
    web-01:
      ansible_host: 192.168.1.10
      ansible_user: root
    web-02:
      ansible_host: 192.168.1.11
      ansible_user: root
```

See `inventory.example.yml` for a template.
