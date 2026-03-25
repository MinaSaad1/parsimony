# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.3.x   | Yes       |
| 0.2.x   | No        |
| 0.1.x   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public issue
2. Email the maintainer or use [GitHub's private vulnerability reporting](https://github.com/MinaSaad1/parsimony/security/advisories/new)
3. Include steps to reproduce the issue
4. Allow reasonable time for a fix before public disclosure

## Scope

Parsimony reads local JSONL files from `~/.claude/projects/` and writes a SQLite cache to `~/.parsimony/`. It makes no network requests and requires no API keys. The primary security considerations are:

- File path traversal when reading session data
- Safe handling of malformed JSONL input
- No execution of content from session files
