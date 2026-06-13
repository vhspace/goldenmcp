// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {MCPRegistry} from "../src/MCPRegistry.sol";

contract MCPRegistryTest is Test {
    MCPRegistry registry;

    function setUp() public {
        registry = new MCPRegistry();
    }

    function test_register_mcp() public {
        uint256 id = registry.register(
            "lifi",
            "https://mcp.lifi.io",
            "walrus://manifest-abc",
            "lifi-quote.goldenmcp.eth"
        );
        assertEq(id, 1);
        MCPRegistry.MCPRecord memory rec = registry.getRecord(1);
        assertEq(rec.name, "lifi");
        assertEq(rec.mcpEndpoint, "https://mcp.lifi.io");
    }

    function test_update_scores() public {
        uint256 id = registry.register("0x", "https://mcp.0x.io", "walrus://x", "0x-quote.goldenmcp.eth");
        registry.updateCapabilityScore(id, "quote", 9000, 8500, 7000, 8500, false, "blob-123");
        MCPRegistry.CapabilityScore memory score = registry.getCapabilityScore(id, "quote");
        assertEq(score.compositeBps, 8500);
        assertFalse(score.failed);
        assertEq(score.walrusBlobId, "blob-123");
    }

    function test_binary_fail_score() public {
        uint256 id = registry.register("bad", "https://bad.io", "walrus://x", "bad.goldenmcp.eth");
        registry.updateCapabilityScore(id, "quote", 0, 0, 0, 0, true, "blob-fail");
        MCPRegistry.CapabilityScore memory score = registry.getCapabilityScore(id, "quote");
        assertTrue(score.failed);
        assertEq(score.compositeBps, 0);
    }

    function test_record_attestation() public {
        uint256 id = registry.register("lifi", "https://mcp.lifi.io", "walrus://x", "lifi.goldenmcp.eth");
        registry.recordAttestation(id, "0xabc123");
        assertEq(registry.getRecord(id).lastAttestationTx, "0xabc123");
    }
}
