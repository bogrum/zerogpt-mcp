# ZeroGPT MCP Server

MCP server that checks text for AI-generated content via ZeroGPT.com.

## Install

```bash
pip install zerogpt-mcp
playwright install chromium
```

Or from source:
```bash
git clone https://github.com/YOUR_USER/zerogpt-mcp
cd zerogpt-mcp
pip install -e .
playwright install chromium
```

## Claude Code Setup

Add to `~/.claude/claude-code.json` or `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "zerogpt": {
      "command": "zerogpt-mcp"
    }
  }
}
```

Or if installed from source:

```json
{
  "mcpServers": {
    "zerogpt": {
      "command": "python",
      "args": ["-m", "zerogpt_mcp.server"],
      "cwd": "/path/to/zerogpt-mcp"
    }
  }
}
```

## Usage in Claude Code

```
Check this text for AI content
Check my report for AI-generated sections
What's the ZeroGPT score for this paragraph?
```

## How It Works

Opens ZeroGPT.com via headless Chromium, pastes the text, and extracts the AI probability score. No API key needed.

## Limitations

- Requires Chromium (installed via `playwright install chromium`)
- ~15K character limit per check
- Rate limited by ZeroGPT.com
- Web scraping — may break if ZeroGPT changes their UI
