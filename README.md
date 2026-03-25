<div align="center">

```
                ██████   █████  ██████  ███████ ██ ██    ██  ██████  ██   ██ ██    ██
                ██   ██ ██   ██ ██   ██ ██      ██ ███  ███ ██    ██ ███  ██  ██  ██
     ▄████▄     ██████  ███████ ██████  ███████ ██ ██ ██ ██ ██    ██ ██ █ ██   ████
    ██ $$ ██    ██      ██   ██ ██   ██      ██ ██ ██    ██ ██    ██ ██  ███    ██
    ██    ██    ██      ██   ██ ██   ██ ███████ ██ ██    ██  ██████  ██   ██    ██
     ▀████▀
      ██  ██    Token usage and cost observability for Claude Code
     ▄██  ██▄
    ▀▀      ▀▀
```

</div>

<p align="center">
  <a href="https://pypi.org/project/parsimony-cli/"><img src="https://img.shields.io/pypi/v/parsimony-cli?color=blue" alt="PyPI"></a>
  <a href="https://pypi.org/project/parsimony-cli/"><img src="https://img.shields.io/pypi/pyversions/parsimony-cli" alt="Python"></a>
  <a href="https://github.com/MinaSaad1/parsimony/blob/main/LICENSE"><img src="https://img.shields.io/github/license/MinaSaad1/parsimony" alt="License"></a>
  <a href="https://github.com/MinaSaad1/parsimony/actions"><img src="https://img.shields.io/github/actions/workflow/status/MinaSaad1/parsimony/ci.yml?branch=main" alt="CI"></a>
</p>

---

## The Problem

You use Claude Code daily. The Anthropic dashboard shows a total bill, but you have no idea:

- Which sessions cost the most?
- Which tools burn through tokens?
- Is prompt caching actually helping?
- How does Opus vs Sonnet usage compare?
- What did that one heavy session actually cost?

**Parsimony answers all of these.** No API keys needed. It reads the JSONL files Claude Code already saves on your machine.

---

## Installation

```bash
pip install parsimony-cli
```

That's it. Requires **Python 3.11+** and **Claude Code** session data at `~/.claude/projects/`.

Other install methods:

```bash
pipx install parsimony-cli    # isolated install
uv tool install parsimony-cli  # with uv
```

Verify it works:

```bash
parsimony --help
```

> If `parsimony` is not in your PATH, use `python -m parsimony` instead.

---

## Quick Start

```bash
parsimony              # today's summary (default)
parsimony yesterday    # yesterday's report
parsimony week         # this week
parsimony week --last  # last week
parsimony month        # this month
parsimony month 2026-03  # specific month
```

---

## Architecture

```
                     ~/.claude/projects/
                            |
                    +-------+-------+
                    |               |
              project-a/       project-b/
              session1.jsonl   session3.jsonl
              session2.jsonl
                    |
                    v
    +=======================================+
    |           P A R S I M O N Y           |
    +=======================================+
    |                                       |
    |   +----------+     +-------------+    |
    |   |  Scanner |---->|   Reader    |    |
    |   | discover |     | stream JSONL|    |
    |   +----------+     +------+------+    |
    |                           |           |
    |                           v           |
    |                  +-----------------+  |
    |                  |Session Builder  |  |
    |                  | dedup requests  |  |
    |                  | detect models   |  |
    |                  | extract tools   |  |
    |                  +--------+--------+  |
    |                           |           |
    |            +--------------+---------+ |
    |            |              |         | |
    |            v              v         v |
    |      +---------+   +--------+ +------+
    |      |  Cost   |   | Group  | |Rollup|
    |      | Engine  |   |  By    | |      |
    |      | Decimal |   |model   | |      |
    |      |precision|   |tool    | |      |
    |      +---------+   |project | |      |
    |            |        |day    | |      |
    |            |        +--------+ +------+
    |            |              |         | |
    |            +--------------+---------+ |
    |                           |           |
    |                           v           |
    |   +----------+   +---------------+    |
    |   |  Cache   |   |    Output     |    |
    |   | SQLite   |   | tables/charts |    |
    |   +----------+   | JSON/CSV      |    |
    |                  +---------------+    |
    +=======================================+
                        |
                        v
              Terminal / Export File
```

### Data Flow

```
  JSONL Events          Parsed Session           Rollup
  +-----------+        +---------------+       +----------+
  |user       |  parse |session_id     | cost  |total_cost|
  |assistant  |------->|segments[]     |------>|per_model |
  |tool_use   |  dedup |  model        | calc  |per_tool  |
  |tool_result|  merge |  calls[]      |       |per_mcp   |
  +-----------+        |    usage      |       |cache_eff |
                       |    tools[]    |       |top_sess  |
                       |subagents[]   |       +----------+
                       +---------------+
```

### Module Map

```
src/parsimony/
  |
  +-- parser/
  |     events.py           # Frozen dataclasses for JSONL event types
  |     scanner.py          # Filesystem discovery of session files
  |     reader.py           # Streaming JSONL line-by-line reader
  |     session_builder.py  # RequestId dedup, model segment detection
  |
  +-- models/
  |     session.py          # Domain model with computed properties
  |     cost.py             # Decimal-precision cost calculation engine
  |     tool_usage.py       # MCP tool name parsing (mcp__server__tool)
  |
  +-- aggregator/
  |     time_range.py       # Today/week/month/custom time windows
  |     grouper.py          # Group by model, tool, project, day
  |     rollup.py           # Full metric aggregation
  |
  +-- output/
  |     formatters.py       # Human-friendly numbers ($1.23, 1.2M, 5m 30s)
  |     tables.py           # Rich tables for every report type
  |     charts.py           # Bar charts, cache gauge
  |     export.py           # JSON and CSV export
  |
  +-- cache/
  |     store.py            # SQLite cache (avoid re-parsing unchanged files)
  |
  +-- cli.py                # Click command group (entry point)
  +-- config.py             # Pricing loader and path helpers
```

---

## Commands

### Reports

```bash
parsimony today              # today's full report
parsimony yesterday          # yesterday's report
parsimony week               # current week
parsimony week --last        # previous week
parsimony month              # current month
parsimony month 2026-03      # specific month
```

Each report shows: total cost, session count, per-model breakdown with cost share, tool usage, MCP servers, daily cost trend, cache efficiency, and a session list sorted by cost.

### Session Drill-Down

```bash
parsimony session a1b2c3d4                              # prefix match
parsimony session a1b2c3d4-5678-9abc-def0-1234567890ab  # full UUID
```

Shows for one session:
- Total cost and duration
- Model segments (Sonnet/Opus/Haiku switches)
- Per-segment token counts (input, output, cache write, cache read)
- Tool breakdown with call counts
- Subagent details
- Cache efficiency

### Rankings

```bash
parsimony top sessions --period week     # most expensive sessions
parsimony top models   --period month    # cost by model
parsimony top tools    --period all      # most used tools
parsimony top projects --period week     # cost by project
parsimony top sessions -n 20            # show top 20
```

### Compare Periods

```bash
parsimony compare --period week  --last 4   # last 4 weeks side-by-side
parsimony compare --period month --last 3   # last 3 months
parsimony compare --period day   --last 7   # last 7 days
```

### Filters and Export

```bash
parsimony -p myproject week                          # filter by project
parsimony --export json month 2026-03 > report.json  # JSON export
parsimony --export csv week > models.csv             # CSV export
parsimony --no-cache today                           # skip cache
parsimony -v today                                   # verbose logging
```

---

## Pricing

Parsimony ships with built-in Claude pricing. Override it at `~/.parsimony/pricing.yaml`:

```yaml
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
```

Unknown models fall back to Sonnet pricing.

---

## How It Works

```
  ~/.claude/projects/e--My-Project/abc123.jsonl
                         |
                  Each line = one event
                         |
     +-------------------+-------------------+
     |                   |                   |
  {"type":"user"    {"type":"assistant"  {"type":"assistant"
   "cwd":"/app"     "model":"sonnet"     "model":"opus"
   "version":"1.0"  "requestId":"r1"     "requestId":"r2"
   ...}             "usage":{...}        "usage":{...}
                    "content":[          ...}
                      {"type":"tool_use"
                       "name":"Read"}
                    ]}
                         |
                         v
              +---------------------+
              | 1. Stream & Parse   |  line-by-line, never loads full file
              | 2. Dedup by reqId   |  last chunk has cumulative usage
              | 3. Detect segments  |  sonnet -> opus = new segment
              | 4. Calculate costs  |  Decimal precision, per-model rates
              | 5. Aggregate        |  by time/model/tool/project
              | 6. Render           |  Rich tables, charts, gauges
              +---------------------+
```

---

## Contributing

```bash
git clone https://github.com/MinaSaad1/parsimony.git
cd parsimony
pip install -e ".[dev]"

# Run tests (170 tests, 91%+ coverage)
pytest

# Lint and type check
ruff check src/
mypy src/
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

Copyright (c) 2026 Parsimony Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
