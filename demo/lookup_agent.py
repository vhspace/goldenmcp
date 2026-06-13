#!/usr/bin/env python3
"""Real x402 lookup agent demo — pays USDC on Arc and receives MCP endpoint."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="GoldenMCP x402 lookup agent")
    parser.add_argument("--capability", required=True)
    parser.add_argument("--min-score", type=float, required=True)
    parser.add_argument("--marketplace-url", default=os.environ.get("MARKETPLACE_URL", "http://localhost:8091"))
    parser.add_argument("--payment-proof", default=os.environ.get("X402_PAYMENT_PROOF", ""))
    args = parser.parse_args()

    url = f"{args.marketplace_url.rstrip('/')}/tools/lookup"
    payload = {"capability": args.capability, "min_score": args.min_score}

    logger.info("lookup %s min_score=%.2f", args.capability, args.min_score)
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, json=payload)
        if response.status_code == 402:
            payment_req = response.json()
            logger.info("payment required: %s", json.dumps(payment_req, indent=2))
            proof = args.payment_proof
            if not proof:
                logger.error(
                    "No payment proof. Complete USDC payment on Arc testnet, "
                    "then re-run with --payment-proof or X402_PAYMENT_PROOF env var."
                )
                sys.exit(1)
            response = client.post(url, json=payload, headers={"X-PAYMENT": proof})
        if response.status_code >= 400:
            logger.error("lookup failed status=%s body=%s", response.status_code, response.text)
            sys.exit(1)
        result = response.json()
        logger.info("lookup result: %s", json.dumps(result, indent=2))
        best = result["results"][0]
        logger.info("best MCP: %s endpoint=%s composite=%.3f", best["ens_name"], best["mcp_endpoint"], best["composite"])


if __name__ == "__main__":
    main()
