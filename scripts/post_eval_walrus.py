#!/usr/bin/env python3
"""Post-eval hook: upload Inspect eval log scores to Walrus.

Usage after `inspect eval`:
  uv run python scripts/post_eval_walrus.py --mcp lifi --capability quote --log path/to/eval.eval
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from goldenmcp_inspect.pipeline import post_eval_from_log_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload eval scores to Walrus after Inspect run")
    parser.add_argument("--mcp", required=True)
    parser.add_argument("--capability", required=True)
    parser.add_argument("--log", required=True, help="Path to Inspect .eval log JSON")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    try:
        result = post_eval_from_log_file(
            args.log,
            args.mcp,
            args.capability,
            run_id=args.run_id,
        )
    except Exception as exc:
        logger.exception("post_eval_walrus failed: %s", exc)
        return 1

    print(
        json.dumps(
            {
                "walrus_manifest_blob_id": result.walrus_manifest_blob_id,
                "walrus_eval_blob_id": result.walrus_eval_blob_id,
                "composite": result.manifest.composite,
                "failed": result.manifest.failed,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
