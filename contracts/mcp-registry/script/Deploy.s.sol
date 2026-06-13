// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {MCPRegistry} from "../src/MCPRegistry.sol";

contract Deploy is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.parseUint(vm.envString("MARKETPLACE_WALLET_PRIVATE_KEY"));
        vm.startBroadcast(deployerPrivateKey);
        MCPRegistry registry = new MCPRegistry();
        vm.stopBroadcast();
        console.log("MCPRegistry deployed at:", address(registry));
    }
}
