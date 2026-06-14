// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {MCPRegistry} from "../src/MCPRegistry.sol";

contract MCPRegistryTest is Test {
    MCPRegistry registry;
    address forwarder = address(0xF0);

    function setUp() public {
        registry = new MCPRegistry(forwarder);
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
        bytes32 transcriptHash = bytes32(uint256(0x0a01));
        registry.recordAttestation(id, "019ea31f-0563", transcriptHash);
        MCPRegistry.MCPRecord memory rec = registry.getRecord(id);
        assertEq(rec.lastAttestationId, "019ea31f-0563");
        assertEq(rec.lastTranscriptHash, transcriptHash);
    }

    function test_onReport_attestation_via_forwarder() public {
        uint256 id = registry.register("lifi", "https://mcp.lifi.io", "walrus://x", "lifi.goldenmcp.eth");
        bytes32 transcriptHash = bytes32(uint256(0x4e5a));
        bytes memory report = abi.encode(uint8(2), id, "019ec38b-6228", transcriptHash);
        vm.prank(forwarder);
        registry.onReport("", report);
        MCPRegistry.MCPRecord memory rec = registry.getRecord(id);
        assertEq(rec.lastAttestationId, "019ec38b-6228");
        assertEq(rec.lastTranscriptHash, transcriptHash);
    }

    function test_onReport_score_via_forwarder() public {
        uint256 id = registry.register("lifi", "https://mcp.lifi.io", "walrus://x", "lifi.goldenmcp.eth");
        bytes memory report =
            abi.encode(uint8(1), id, "quote", uint16(9200), uint16(8500), uint16(7000), uint16(8600), false, "blob-xyz");
        vm.prank(forwarder);
        registry.onReport("", report);
        MCPRegistry.CapabilityScore memory score = registry.getCapabilityScore(id, "quote");
        assertEq(score.compositeBps, 8600);
        assertEq(score.walrusBlobId, "blob-xyz");
    }

    function test_supportsInterface() public view {
        assertTrue(registry.supportsInterface(0x01ffc9a7)); // ERC-165
        assertTrue(registry.supportsInterface(MCPRegistry.onReport.selector)); // IReceiver
        assertFalse(registry.supportsInterface(0xffffffff));
    }

    function test_onReport_rejects_non_forwarder() public {
        uint256 id = registry.register("lifi", "https://mcp.lifi.io", "walrus://x", "lifi.goldenmcp.eth");
        bytes memory report = abi.encode(uint8(2), id, "x", bytes32(uint256(1)));
        vm.expectRevert(abi.encodeWithSelector(MCPRegistry.UnauthorizedForwarder.selector, address(this)));
        registry.onReport("", report);
    }
}
