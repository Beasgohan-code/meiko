# Meiko CLI

A lightweight terminal client for the Meiko Agent backend — chat, switch agent
modes, manage provider API keys, and download generated files, all from the
command line.

## Install

```bash
cd cli
pip install -r requirements.txt
```

## Usage

```bash
# One-off message (autonomous mode by default)
python meiko_cli.py chat "Summarize the latest AI news"

# Use a specific agent mode
python meiko_cli.py chat --mode research "What's new in fusion energy this month?"
python meiko_cli.py chat --mode code "Write a Python script that renames all .txt files in a folder to .md"

# Interactive REPL (switch modes on the fly with /mode <name>)
python meiko_cli.py repl

# List available model providers / agent modes
python meiko_cli.py providers
python meiko_cli.py modes

# Store an API key on the server (e.g. your free NVIDIA NIM key)
python meiko_cli.py set-key nvidia nvapi-xxxxxxxxxxxxxxxx

# Download a file Meiko generated during a session (e.g. a zip export)
python meiko_cli.py download <session_id> meiko_export_169999.zip -o export.zip
```

Point the CLI at a remote/deployed backend:

```bash
python meiko_cli.py --server https://your-meiko-backend.example.com --user alice chat "hello"
```

Or set environment variables once:

```bash
export MEIKO_SERVER=https://your-meiko-backend.example.com
export MEIKO_USER=alice
python meiko_cli.py chat "hello"
```
