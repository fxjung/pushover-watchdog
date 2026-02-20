# Pushover memory/disk usage watchdog

```bash
uv tool install git+https://github.com/fxjung/pushover-watchdog
watchdog-install-service
```

Edit secrets at
```bash
vim ~/.config/pushover-watchdog/env
```

Check logs with
```bash
journalctl --user -u watchdog.service -f
```
