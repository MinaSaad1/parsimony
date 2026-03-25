# Parsimony

**Know where every token goes.**

Parsimony is a CLI tool that reads Claude Code's local session files and shows you exactly where your tokens and money are spent. Per API call, per tool, per MCP server, per subagent, with full model segment tracking.

## The Problem

You use Claude Code daily. The Anthropic dashboard shows a total bill, but you have no idea:

- Which sessions cost the most?
- Which tools burn through tokens?
- Is prompt caching actually helping?
- How does Opus vs Sonnet usage compare?
- What did that one heavy session actually cost?

Parsimony answers all of these. No API keys needed. It reads the JSONL files Claude Code already saves on your machine.

---

## Prerequisites

- **Python 3.11 or higher**
- **Claude Code** installed and used (it creates session files at `~/.claude/projects/`)

To verify you have session data:

```bash
# Check if Claude Code session files exist
ls ~/.claude/projects/
```

You should see directories with names like `e--Coding-Projects-MyApp`. Each contains `.jsonl` session files.

---

## Installation

### Option 1: Install from GitHub (current)

```bash
# Clone the repository
git clone https://github.com/your-username/parsimony.git
cd parsimony

# Install
pip install .

# Or install in editable mode for development
pip install -e .
```

### Option 2: Install from PyPI (coming soon)

```bash
pip install parsimony

# Or with pipx (isolated install, recommended for CLI tools)
pipx install parsimony

# Or with uv
uv tool install parsimony
```

### Verify installation

```bash
parsimony --help
```

You should see:

```
Usage: parsimony [OPTIONS] COMMAND [ARGS]...

  Parsimony: Know where every token goes.

Options:
  -p, --project TEXT   Filter by project name (substring match).
  --export [json|csv]  Export report as JSON or CSV.
  --no-cache           Disable session cache.
  -v, --verbose        Enable verbose logging.
  --help               Show this message and exit.

Commands:
  compare    Compare usage across multiple time periods side-by-side.
  month      Show monthly usage report.
  session    Show detailed breakdown for a specific session.
  today      Show today's usage report.
  top        Show top items by a given dimension.
  week       Show weekly usage report.
  yesterday  Show yesterday's usage report.
```

If `parsimony` is not found in your PATH, use `python -m parsimony` instead.

---

## Usage

### Daily Reports

```bash
# Today's usage (also the default when you just run `parsimony`)
parsimony today

# Yesterday
parsimony yesterday
```

Shows: total cost, session count, API calls, per-model breakdown with cost share, tool usage, MCP server activity, and cache efficiency.

### Weekly and Monthly Reports

```bash
# Current week
parsimony week

# Last week
parsimony week --last

# Current month
parsimony month

# A specific month
parsimony month 2026-03
```

Weekly/monthly reports include a daily cost trend chart and a full session list sorted by cost.

### Session Drill-Down

Every session has a UUID. You can see them in the session list, or look at filenames in `~/.claude/projects/`.

```bash
# Full session ID
parsimony session a1b2c3d4-5678-9abc-def0-1234567890ab

# Or just a prefix (minimum 8 chars)
parsimony session a1b2c3d4
```

Shows for that single session:
- Total cost
- Each model segment (when you switched between Sonnet/Opus/Haiku)
- Per-segment token counts (input, output, cache write, cache read)
- Every tool used and how many times
- Subagent details (tokens, tool count, duration)
- Cache efficiency percentage

### Top Rankings

```bash
# Most expensive sessions this week
parsimony top sessions --period week

# Cost by model this month
parsimony top models --period month

# Most used tools (all time)
parsimony top tools --period all

# Cost by project this week
parsimony top projects --period week

# Show top 20 instead of default 10
parsimony top sessions --period month -n 20
```

Period options: `day`, `week`, `month`, `all`

### Compare Time Periods

```bash
# Compare last 4 weeks side by side
parsimony compare --period week --last 4

# Compare last 3 months
parsimony compare --period month --last 3

# Compare last 7 days
parsimony compare --period day --last 7
```

Shows sessions, total cost, total tokens, average cost per session, and cache efficiency for each period in columns.

### Filter by Project

```bash
# Only show sessions from a specific project (substring match)
parsimony -p myproject week
parsimony -p "Coding Projects" month
```

### Export Data

```bash
# Export as JSON
parsimony --export json month 2026-03 > march-report.json

# Export as CSV (per-model breakdown)
parsimony --export csv week > weekly-models.csv

# Export a session comparison
parsimony --export json compare --period week --last 4 > comparison.json
```

JSON export includes: session count, total tokens, total cost, per-model breakdown (tokens + cost), per-tool breakdown, and MCP server usage.

---

## Customizing Pricing

Parsimony ships with current Claude model pricing baked in. When Anthropic changes prices, or if you want to track custom rates, create a pricing override file:

```bash
# Create the config directory
mkdir -p ~/.parsimony

# Create your pricing file
cat > ~/.parsimony/pricing.yaml << 'EOF'
models:
  claude-opus-4-6:
    input_per_million: 15.00
    output_per_million: 75.00
    cache_write_per_million: 18.75
    cache_read_per_million: 1.50
  claude-sonnet-4-6:
    input_per_million: 3.00
    output_per_million: 15.00
    cache_write_per_million: 3.75
    cache_read_per_million: 0.30
  claude-haiku-4-5-20251001:
    input_per_million: 0.80
    output_per_million: 4.00
    cache_write_per_million: 1.00
    cache_read_per_million: 0.08
EOF
```

Models not listed in the pricing file fall back to Sonnet pricing (with a warning when `--verbose` is enabled).

---

## Caching

Parsimony caches parsed session data in a SQLite database at `~/.parsimony/cache.db`. This makes repeated queries much faster since session files only need to be parsed once.

The cache automatically invalidates when a session file changes (checked by file size and modification time).

```bash
# Skip the cache (force re-parsing all files)
parsimony --no-cache today

# The cache file can be safely deleted at any time
rm ~/.parsimony/cache.db
```

---

## How It Works

Claude Code stores every session as a JSONL file at:

```
~/.claude/projects/{encoded-project-path}/{session-uuid}.jsonl
```

Each line is a JSON event (user message, assistant response, tool use, etc.). Parsimony:

1. **Scans** `~/.claude/projects/` to discover all project directories and session files
2. **Streams** each JSONL file line-by-line (never loads entire files into memory)
3. **Deduplicates** streaming chunks (multiple entries share the same requestId; the last chunk has cumulative usage)
4. **Detects model segments** when you switch between Sonnet, Opus, and Haiku mid-session
5. **Calculates costs** using Decimal precision with per-model pricing rates
6. **Aggregates** by time period, model, tool, MCP server, or project
7. **Renders** rich terminal output with tables, bar charts, and gauges

---

## Development

```bash
git clone https://github.com/your-username/parsimony.git
cd parsimony

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests (170 tests, 91%+ coverage)
pytest

# Lint
ruff check src/

# Type check (strict mode)
mypy src/
```

---

## License

MIT
