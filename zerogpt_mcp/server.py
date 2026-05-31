#!/usr/bin/env python3
"""ZeroGPT MCP Server — AI content detection via ZeroGPT.com"""

import json
import sys
import time
import re
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationCapabilities
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
    """Internal: Submit text to ZeroGPT and return AI score."""
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

        page.wait_for_selector("[class*='percentage'], [class*='score'], [class*='result']", timeout=timeout_ms)
        time.sleep(3)

        result = {}
        page_content = page.content()

        percentages = re.findall(r"(\d+(?:\.\d+)?)\s*%\s*(?:AI|Artificial)", page_content, re.IGNORECASE)
        if not percentages:
            percentages = re.findall(r"(?:AI|Artificial)[^%]*?(\d+(?:\.\d+)?)\s*%", page_content, re.IGNORECASE)
        if percentages:
            result["ai_probability_pct"] = float(percentages[0])

        score_elements = page.locator("[class*='percentage'], [class*='score'], [class*='result-value']").all()
        for el in score_elements:
            txt = el.text_content()
            if txt and "%" in txt:
                nums = re.findall(r"(\d+(?:\.\d+)?)\s*%", txt)
                if nums:
                    result["ai_probability_pct"] = float(nums[0])
                    break

        if not result:
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
        response = f"ZeroGPT AI Score: {score:.1f}%\n"
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
            InitializationCapabilities(
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
