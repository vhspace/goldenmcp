// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {MCPRegistry} from "../src/MCPRegistry.sol";

contract Deploy is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.parseUint(vm.envString("MARKETPLACE_WALLET_PRIVATE_KEY"));
        // CRE KeystoneForwarder allowed to call onReport. For `cre workflow simulate
        // --broadcast` this is the MockKeystoneForwarder; set MCP_REGISTRY_FORWARDER.
        address forwarder = vm.envOr("MCP_REGISTRY_FORWARDER", address(0));
        vm.startBroadcast(deployerPrivateKey);
        MCPRegistry registry = new MCPRegistry(forwarder);
        vm.stopBroadcast();
        console.log("MCPRegistry deployed at:", address(registry));
        console.log("forwarder:", forwarder);
    }
}
