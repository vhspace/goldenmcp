"""CLI: smoke-test all vendor MCPs (list_tools + read-only probe)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from goldenmcp_web_agent.vendor_mcp import VENDOR_NAMES, smoke_all_vendors

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe all vendor MCPs used by the concierge")
    parser.add_argument(
        "--vendor",
        action="append",
        dest="vendors",
        help=f"Probe one vendor (repeatable). Default: all {VENDOR_NAMES}",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON array of probe results")
    args = parser.parse_args()

    vendors = tuple(args.vendors) if args.vendors else VENDOR_NAMES
    results = asyncio.run(smoke_all_vendors(vendors=vendors))

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        for r in results:
            status = "OK" if r.ok else "FAIL"
            line = f"[{status}] {r.vendor}: tools={r.tool_count}"
            if r.probe_tool:
                line += f" probe={r.probe_tool}"
            print(line)
            if r.tools:
                print(f"       listed: {', '.join(r.tools[:8])}{'…' if len(r.tools) > 8 else ''}")
            if r.probe_preview:
                print(f"       preview: {r.probe_preview}")
            if r.error:
                print(f"       error: {r.error}", file=sys.stderr)

    failed = [r.vendor for r in results if not r.ok]
    if failed:
        logger.error("vendor MCP smoke failed for: %s", ", ".join(failed))
        return 1
    logger.info("all %s vendor MCP probes passed", len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
