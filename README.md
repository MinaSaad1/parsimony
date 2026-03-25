<div align="center">

```
 ██████╗  █████╗ ██████╗ ███████╗██╗███╗   ███╗ ██████╗ ███╗   ██╗██╗   ██╗
 ██╔══██╗██╔══██╗██╔══██╗██╔════╝██║████╗ ████║██╔═══██╗████╗  ██║╚██╗ ██╔╝
 ██████╔╝███████║██████╔╝███████╗██║██╔████╔██║██║   ██║██╔██╗ ██║ ╚████╔╝
 ██╔═══╝ ██╔══██║██╔══██╗╚════██║██║██║╚██╔╝██║██║   ██║██║╚██╗██║  ╚██╔╝
 ██║     ██║  ██║██║  ██║███████║██║██║ ╚═╝ ██║╚██████╔╝██║ ╚████║   ██║
 ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝
```

<strong>Token usage and cost observability for Claude Code</strong>

</div>

<p align="center">
  <a href="https://pypi.org/project/parsimony-cli/"><img src="https://img.shields.io/pypi/v/parsimony-cli?color=blue" alt="PyPI"></a>
  <a href="https://pypi.org/project/parsimony-cli/"><img src="https://img.shields.io/pypi/pyversions/parsimony-cli" alt="Python"></a>
  <a href="https://github.com/MinaSaad1/parsimony/blob/main/LICENSE"><img src="https://img.shields.io/github/license/MinaSaad1/parsimony" alt="License"></a>
  <a href="https://github.com/MinaSaad1/parsimony/actions"><img src="https://img.shields.io/github/actions/workflow/status/MinaSaad1/parsimony/ci.yml?branch=main" alt="CI"></a>
</p>

---

You use Claude Code daily but have no idea which sessions cost the most, which tools burn tokens, or whether caching is helping. **Parsimony answers all of these.** No API keys needed. It reads the JSONL files Claude Code already saves on your machine.

---

## Example Output

<div align="center">
  <picture>
    <img alt="Parsimony output example" src="assets/demo.svg" width="680">
  </picture>
</div>

---

## Install

```bash
pip install parsimony-cli
```

<details>
<summary>Other methods</summary>

```bash
pipx install parsimony-cli     # isolated install
uv tool install parsimony-cli  # with uv
python -m parsimony            # if not in PATH
```

</details>

---

## Usage

```bash
parsimony                # today's summary (default)
parsimony yesterday      # yesterday's report
parsimony week           # this week
parsimony week --last    # last week
parsimony month          # this month
parsimony month 2026-03  # specific month
```

### Session Drill-Down

```bash
parsimony session a1b2c3d4   # prefix match or full UUID
```

### Rankings

```bash
parsimony top sessions --period week    # most expensive sessions
parsimony top models   --period month   # cost by model
parsimony top tools    --period all     # most used tools
parsimony top projects --period week    # cost by project
```

### Compare Periods

```bash
parsimony compare --period week  --last 4   # last 4 weeks side-by-side
parsimony compare --period month --last 3   # last 3 months
```

### Export

```bash
parsimony --export json month > report.json
parsimony --export csv week > models.csv
```

---

## How It Works

```mermaid
graph LR
    A["~/.claude/projects/*.jsonl"] --> B["Scanner"]
    B --> C["Reader"]
    C --> D["Session Builder"]
    D --> E["Cost Engine"]
    D --> F["Grouper"]
    E --> G["Rollup"]
    F --> G
    G --> H["Rich Tables & Charts"]
    G --> I["JSON / CSV Export"]
    H --> J["Terminal"]
    I --> K["File"]

    style A fill:#1e3a5f,stroke:#22d3ee,color:#22d3ee
    style B fill:#1a1a2e,stroke:#8b949e,color:#e6edf3
    style C fill:#1a1a2e,stroke:#8b949e,color:#e6edf3
    style D fill:#1a1a2e,stroke:#8b949e,color:#e6edf3
    style E fill:#1a1a2e,stroke:#e879f9,color:#e879f9
    style F fill:#1a1a2e,stroke:#e879f9,color:#e879f9
    style G fill:#1a1a2e,stroke:#4ade80,color:#4ade80
    style H fill:#1a1a2e,stroke:#22d3ee,color:#22d3ee
    style I fill:#1a1a2e,stroke:#22d3ee,color:#22d3ee
    style J fill:#1e3a5f,stroke:#22d3ee,color:#22d3ee
    style K fill:#1e3a5f,stroke:#22d3ee,color:#22d3ee
```

### Data Pipeline

```mermaid
graph TD
    subgraph Parse
        A["JSONL line-by-line"] --> B["Dedup by requestId"]
        B --> C["Detect model switches"]
        C --> D["Extract tool usage"]
    end

    subgraph Calculate
        D --> E["Decimal-precision costs"]
        E --> F["Group by model / tool / project / day"]
        F --> G["Cache efficiency metrics"]
    end

    subgraph Output
        G --> H["Rich tables"]
        G --> I["Bar charts & gauges"]
        G --> J["JSON / CSV"]
    end

    style A fill:#0d1117,stroke:#22d3ee,color:#22d3ee
    style B fill:#0d1117,stroke:#22d3ee,color:#22d3ee
    style C fill:#0d1117,stroke:#22d3ee,color:#22d3ee
    style D fill:#0d1117,stroke:#22d3ee,color:#22d3ee
    style E fill:#0d1117,stroke:#e879f9,color:#e879f9
    style F fill:#0d1117,stroke:#e879f9,color:#e879f9
    style G fill:#0d1117,stroke:#e879f9,color:#e879f9
    style H fill:#0d1117,stroke:#4ade80,color:#4ade80
    style I fill:#0d1117,stroke:#4ade80,color:#4ade80
    style J fill:#0d1117,stroke:#4ade80,color:#4ade80
```

### What Each Report Shows

| Section | Details |
|---------|---------|
| **Summary** | Total cost, session count, API calls |
| **By Model** | Per-model tokens, cost, share % |
| **By Tool** | Tool call counts, MCP vs built-in |
| **Cache** | Hit rate gauge, read/write breakdown |
| **Sessions** | Time, duration, project, model, cost |

---

## Pricing

Built-in pricing for all Claude models. Override at `~/.parsimony/pricing.yaml`:

<details>
<summary>Default pricing table</summary>

| Model | Input | Output | Cache Write | Cache Read |
|-------|------:|-------:|------------:|-----------:|
| Opus 4.6 | $5.00/M | $25.00/M | $6.25/M | $0.50/M |
| Sonnet 4.6 | $3.00/M | $15.00/M | $3.75/M | $0.30/M |
| Haiku 4.5 | $1.00/M | $5.00/M | $1.25/M | $0.10/M |

Unknown models fall back to Sonnet pricing.

</details>

---

## Project Structure

```mermaid
graph TD
    CLI["cli.py - Click entry point"] --> Parser
    CLI --> Models
    CLI --> Aggregator
    CLI --> Output
    CLI --> Cache

    subgraph Parser
        P1["scanner.py - discover files"]
        P2["reader.py - stream JSONL"]
        P3["session_builder.py - dedup & segments"]
        P4["events.py - frozen dataclasses"]
    end

    subgraph Models
        M1["session.py - domain model"]
        M2["cost.py - Decimal engine"]
        M3["tool_usage.py - MCP parsing"]
    end

    subgraph Aggregator
        A1["time_range.py - time windows"]
        A2["grouper.py - group by dimension"]
        A3["rollup.py - full aggregation"]
    end

    subgraph Output
        O1["tables.py - Rich tables"]
        O2["charts.py - bar charts & gauge"]
        O3["formatters.py - $1.23, 1.2M"]
        O4["export.py - JSON & CSV"]
    end

    subgraph Cache
        C1["store.py - SQLite cache"]
    end

    style CLI fill:#1e3a5f,stroke:#22d3ee,color:#22d3ee
    style Parser fill:#0d1117,stroke:#8b949e,color:#e6edf3
    style Models fill:#0d1117,stroke:#e879f9,color:#e6edf3
    style Aggregator fill:#0d1117,stroke:#4ade80,color:#e6edf3
    style Output fill:#0d1117,stroke:#facc15,color:#e6edf3
    style Cache fill:#0d1117,stroke:#60a5fa,color:#e6edf3
```

---

## Contributing

```bash
git clone https://github.com/MinaSaad1/parsimony.git
cd parsimony
pip install -e ".[dev]"
pytest                # 170 tests, 91%+ coverage
ruff check src/       # lint
mypy src/             # type check
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
