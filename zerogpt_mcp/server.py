#!/usr/bin/env python3
"""ZeroGPT MCP Server — AI content detection via ZeroGPT.com"""

import json
import sys
import time
import re
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("zerogpt-mcp")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="check_zerogpt",
            description="Check text for AI-generated content using ZeroGPT.com. Returns the AI probability score (0-100%).",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to check for AI-generated content (max ~15,000 characters)"
                    }
                },
                "required": ["text"]
            }
        )
    ]

def _check_zerogpt(text: str, timeout_ms: int = 60000) -> dict:
    """Internal: Submit text to ZeroGPT and return AI score.

    Uses targeted CSS selectors against ZeroGPT's result DOM instead of
    regex-searching the full page HTML, which previously matched CSS
    percentages, ad copy, or embedded data unrelated to the AI score.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"error": "playwright not installed. Run: pip install playwright && playwright install chromium"}

    text = text[:15000]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.zerogpt.com", timeout=30000)
        page.wait_for_selector("textarea", timeout=15000)

        textarea = page.locator("textarea").first
        textarea.fill(text)

        detect_btn = page.locator("button:has-text('Detect')").first
        detect_btn.click()

        # Wait for the specific result element that holds the AI percentage.
        # ZeroGPT renders: <div class="percentage-div"><span class="header-text">N%AI GPT*</span></div>
        page.wait_for_selector(".percentage-div span.header-text", timeout=timeout_ms)
        time.sleep(2)  # Let gauge animation settle

        result = {}

        # Primary: extract from the dedicated percentage span
        pct_span = page.locator(".percentage-div span.header-text").first
        span_text = pct_span.text_content().strip() if pct_span else ""
        # Text is like "11.3%AI GPT*" or "0%AI GPT*"
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", span_text)
        if pct_match:
            result["ai_probability_pct"] = float(pct_match.group(1))

        # Also capture the human/mixed/AI verdict from the sibling header
        verdict_span = page.locator(".final-result > span.header-text").first
        if verdict_span:
            verdict_text = verdict_span.text_content().strip()
            result["verdict_text"] = verdict_text[:200]

        # Fallback: search only within the result card, not the full page
        if "ai_probability_pct" not in result:
            result_card = page.locator(".card.result-card").first
            if result_card:
                card_text = result_card.text_content()
                match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*AI\s*GPT", card_text, re.IGNORECASE)
                if match:
                    result["ai_probability_pct"] = float(match.group(1))

        # Last resort: raw body text for debugging
        if "ai_probability_pct" not in result:
            result["raw_text"] = page.locator("body").text_content()[:500]

        page.close()
        browser.close()

    return result

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name != "check_zerogpt":
        raise ValueError(f"Unknown tool: {name}")

    text = arguments.get("text", "")
    if not text:
        return [TextContent(type="text", text="Error: No text provided")]

    result = _check_zerogpt(text)

    if "error" in result:
        return [TextContent(type="text", text=f"Error: {result['error']}")]

    score = result.get("ai_probability_pct", None)
    if score is not None:
        verdict = result.get("verdict_text", "")
        response = f"ZeroGPT AI Score: {score:.1f}%\n"
        if verdict:
            response += f"ZeroGPT Verdict: {verdict}\n"
        if score < 20:
            response += "Assessment: Likely human-written"
        elif score < 50:
            response += "Assessment: Mixed — some AI patterns detected"
        elif score < 80:
            response += "Assessment: Significant AI content detected"
        else:
            response += "Assessment: Very likely AI-generated"
        return [TextContent(type="text", text=response)]
    else:
        return [TextContent(type="text", text=f"Could not extract score. Raw text: {result.get('raw_text', 'N/A')[:300]}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                sampling={},
                experimental={},
                roots={}
            ),
            NotificationOptions()
        )

def cli_main():
    import anyio
    anyio.run(main)

if __name__ == "__main__":
    cli_main()
