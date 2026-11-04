# Setup on the Evo X2 (paper copy-trading)

Everything below is paper mode: the bot never places a real order.

## 1. Rivo API key (required: the live trade feed)

1. Sign up at https://rivo.markets and subscribe ($15/month or $9/week).
2. Go to Settings, then API keys, and create a key with the **read** scope.
   It starts with `rivo_live_` and is shown once, so copy it now.

## 2. Kalshi API key (optional for paper; needed later for live)

Paper mode only reads public Kalshi prices, so it needs no key. Create one now to check your account and be
ready for live trading:

1. Log in at https://kalshi.com, open your account or profile settings, and find **API Keys**.
   Choose **Create new API key**.
2. Save the **Key ID** and download the **private key** file. Kalshi shows it once.
3. On the Evo X2, store the key:

   ```bash
   mkdir -p ~/.kalshi && mv ~/Downloads/*.key ~/.kalshi/kalshi.pem && chmod 600 ~/.kalshi/kalshi.pem
   ```

   The downloaded file may end in `.txt` or `.pem` instead of `.key`. Adjust the name if so.

## 3. Install

On Linux (Ubuntu or Debian). On Windows, install WSL first (`wsl --install` in an admin PowerShell, then reboot)
and run the rest inside Ubuntu.

```bash
sudo apt update && sudo apt install -y git python3 python3-venv
```

```bash
git clone -b claude/kind-bohr-iv7y71 https://github.com/reecegitshubsonit/backtest-ceo.git ~/backtest-ceo
```

The repo is private, so git asks for your GitHub username and a personal access token as the password
(github.com, then Settings, Developer settings, Personal access tokens). Alternatively, run `gh auth login` first.

```bash
cd ~/backtest-ceo/kalshi && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
cp copy_config.example.json copy_config.json && cp config.example.json config.json
```

## 4. Keys file

```bash
cat > ~/.kalshibot.env <<'EOF'
RIVO_API_KEY=rivo_live_PASTE_HERE
KALSHI_API_KEY_ID=PASTE_KEY_ID_HERE
KALSHI_PRIVATE_KEY_PATH=/home/YOUR_USER/.kalshi/kalshi.pem
EOF
chmod 600 ~/.kalshibot.env
```

Load it in the current shell:

```bash
set -a && . ~/.kalshibot.env && set +a
```

## 5. Check

```bash
cd ~/backtest-ceo/kalshi && .venv/bin/python -m pytest -q
```

This command needs the Kalshi key. It should print your balance:

```bash
.venv/bin/python -m kalshibot account
```

Refresh the trader picks (optional; the defaults are the 2026-11-03 picks):

```bash
.venv/bin/python -m kalshibot leaders --refresh --write copy_config.json
```

## 6. Run the copy bot

```bash
.venv/bin/python -m kalshibot copy stream
```

You should see `streaming 7 traders from Rivo (paper copy): ...`. Each copied or skipped trade prints one line.
In another terminal:

```bash
cd ~/backtest-ceo/kalshi && .venv/bin/python -m kalshibot copy status
```

## 7. Keep it running (starts on boot, restarts on crash)

```bash
mkdir -p ~/.config/systemd/user && cat > ~/.config/systemd/user/kalshibot-copy.service <<'EOF'
[Unit]
Description=kalshibot paper copy stream
After=network-online.target

[Service]
WorkingDirectory=%h/backtest-ceo/kalshi
EnvironmentFile=%h/.kalshibot.env
ExecStart=%h/backtest-ceo/kalshi/.venv/bin/python -u -m kalshibot copy stream
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF
```

```bash
systemctl --user daemon-reload && systemctl --user enable --now kalshibot-copy && sudo loginctl enable-linger $USER
```

Follow the logs:

```bash
journalctl --user -u kalshibot-copy -f
```

Optional, the second strategy (favorite-side maker, paper):

```bash
.venv/bin/python -m kalshibot paper
```

## 8. What to watch

- `data/copy_journal.jsonl` has every copy and skip, with the leader's price, our fill, slippage, delay and P&L.
- After 2–4 weeks, drop traders whose *copied* P&L is negative before going live.
- If many lines say `stale`, Rivo's delay is longer than `max_age_sec` (300) in `copy_config.json`.
