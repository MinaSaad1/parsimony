# Changelog

## 0.3.2 (2026-03-26)

### Removed

- **Built-in tier presets** (`--tier pro|max5|max20`) removed. Anthropic's limits are compute-weighted, not raw token counts, so hardcoded presets were inaccurate. Set your own limits in `~/.parsimony/config.yaml` based on your actual usage page.

### Changed

- **Demo and dashboard SVGs** updated to show token-first output with generic project names and correct model share percentages

## 0.3.0 (2026-03-26)

Usage-first reframing. All output now leads with token usage; cost is opt-in via `--show-cost`.

### Features

- **Token-first presentation** across all tables, charts, dashboard, and diffs
- **`--show-cost` flag** to include API cost estimate columns (hidden by default)
- **Token budgets** with custom session and weekly limits in `~/.parsimony/config.yaml`
- **Usage gauges** showing progress bars against session peak and weekly token limits
- **Token-based filtering** with `--min-tokens` and `--max-tokens` flags
- **Token trend analysis** with `moving_average_tokens()` and `trend_direction_tokens()`
- **`DisplayConfig`** dataclass flows through all render functions to control cost visibility
- **`SessionRollup`** gains 7 new token aggregate fields (input/output/cache breakdown, averages, peak)
- **Dashboard gauge widgets** (`UsageGauge`, `SessionPeakGauge`) for live token limit tracking

### Breaking Changes

- Default output no longer shows cost columns (use `--show-cost` to restore)
- `CostHeader` widget renamed to `UsageHeader`
- CSS id `#cost-header` renamed to `#usage-header`

## 0.2.0 (2026-03-25)

### Features

- **Filtering** by model, tool, and cost ranges (`--model`, `--tool`, `--min-cost`, `--max-cost`)
- **Budget alerts** with daily, weekly, and monthly cost thresholds
- **Cost trends** with daily bars, 7-day moving averages, and direction detection
- **Session diff** for side-by-side comparison of two sessions
- **Live terminal dashboard** with auto-refreshing Textual TUI
- **MCP tool breakdown** showing per-server tool call counts

## 0.1.0 (2026-03-25)

Initial release.

### Features

- **Daily reports** with total cost, session count, and API call metrics
- **Per-model breakdown** showing tokens, cost, and share percentage
- **Tool usage tracking** with call counts and MCP vs built-in classification
- **Cache efficiency gauge** showing hit rate with visual progress bar
- **Session list** with time, duration, project, and model info
- **Session drill-down** with model segments, per-call token counts, and subagent details
- **Time range filtering**: today, yesterday, week, month, or custom month
- **Rankings**: top sessions, models, tools, and projects
- **Period comparison**: side-by-side weekly, monthly, or daily comparisons
- **Project filtering** with `--project` flag
- **Export** to JSON or CSV
- **SQLite caching** to avoid re-parsing unchanged session files
- **Custom pricing** via `~/.parsimony/pricing.yaml`
- Built-in pricing for Claude Opus 4.6, Sonnet 4.6, and Haiku 4.5
