# Running Codex locally in this repository

This project expects Codex to read `.codex/config.toml` from the repo root.

## 1) Open the repo

```bash
cd /workspace/qDiffusion_UP
```

## 2) Start Codex with repo config

```bash
codex
```

Codex will automatically load `.codex/config.toml` from this directory.

## 3) One-shot task example

```bash
codex run "Audit the launcher startup path for runtime git clone behavior and report findings."
```

## 4) Explicit config path example

If you want to force a config file path explicitly:

```bash
codex --config .codex/config.toml
```

## Notes
- The repo config pins model/reasoning and limits environment passthrough.
- `PYTHONPATH` is intentionally **not** forwarded by config.
