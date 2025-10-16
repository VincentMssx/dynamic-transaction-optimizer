// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "../lib/forge-std/src/Script.sol";
import {console} from "../lib/forge-std/src/console.sol";
import {TransactionManager} from "../src/TransactionManager.sol";

contract DeployTransactionManager is Script {
    function run() external returns (TransactionManager) {
        // --- 1. Load configuration from environment variables ---
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address executorAddress = vm.envAddress("EXECUTOR_ADDRESS");

        // Check for missing environment variables
        require(deployerPrivateKey != 0, "PRIVATE_KEY must be set in .env file");
        require(executorAddress != address(0), "EXECUTOR_ADDRESS must be set in .env file");

        // --- 2. Start broadcasting transactions ---
        // This tells Foundry that any state changes from here on should be
        // sent as real transactions to the specified network.
        vm.startBroadcast(deployerPrivateKey);

        // --- 3. Deploy the contract ---
        console.log("Deploying TransactionManager...");
        TransactionManager manager = new TransactionManager();
        console.log("TransactionManager deployed at:", address(manager));

        // --- 4. Transfer ownership to the executor address ---
        // This is a critical step for security.
        console.log("Transferring ownership to executor:", executorAddress);
        manager.transferOwnership(executorAddress);
        console.log("Ownership transferred.");

        // --- 5. Stop broadcasting ---
        vm.stopBroadcast();

        return manager;
    }
}
