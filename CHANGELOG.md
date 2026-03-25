# Changelog

## 0.1.0 (2026-03-25)

Initial release.

### Features

- **Daily reports** with total cost, session count, and API call metrics
- **Per-model breakdown** showing tokens, cost, and share percentage
- **Tool usage tracking** with call counts and MCP vs built-in classification
- **Cache efficiency gauge** showing hit rate with visual progress bar
- **Session list** sorted by cost with time, duration, project, and model info
- **Session drill-down** with model segments, per-call token counts, and subagent details
- **Time range filtering**: today, yesterday, week, month, or custom month
- **Rankings**: top sessions, models, tools, and projects by cost
- **Period comparison**: side-by-side weekly, monthly, or daily comparisons
- **Project filtering** with `--project` flag
- **Export** to JSON or CSV
- **SQLite caching** to avoid re-parsing unchanged session files
- **Custom pricing** via `~/.parsimony/pricing.yaml`
- Built-in pricing for Claude Opus 4.6, Sonnet 4.6, and Haiku 4.5
