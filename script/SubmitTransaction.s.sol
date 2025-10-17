// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {TransactionManager} from "../src/TransactionManager.sol";

contract SubmitTransaction is Script {
    function run() external {
        // Load the contract address from an environment variable
        address contractAddress = vm.envAddress("CONTRACT_ADDRESS");
        require(contractAddress != address(0), "CONTRACT_ADDRESS must be set in .env file");

        // Create an instance of the TransactionManager contract
        TransactionManager manager = TransactionManager(contractAddress);

        // Define the transaction parameters
        address targetContract = vm.envAddress("TARGET_CONTRACT_ADDRESS");
        require(targetContract != address(0), "TARGET_CONTRACT_ADDRESS must be set in .env file");

        bytes memory data = "0x";
        uint256 maxGasPrice = 20 gwei;
        uint256 deadline = block.timestamp + 1 hours;

        // Start broadcasting transactions
        uint256 submitterPrivateKey = vm.envUint("SUBMITTER_PRIVATE_KEY");
        require(submitterPrivateKey != 0, "SUBMITTER_PRIVATE_KEY must be set in .env file");
        vm.startBroadcast(submitterPrivateKey);

        // Submit the transaction
        manager.submitTransaction(targetContract, data, maxGasPrice, deadline);

        // Stop broadcasting
        vm.stopBroadcast();
    }
}
