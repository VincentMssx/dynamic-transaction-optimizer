// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "../lib/forge-std/src/Test.sol";
import {DeployTransactionManager} from "../script/Deploy.s.sol";
import {TransactionManager} from "../src/TransactionManager.sol";

// @title DeployTransactionManagerTest
// @notice This test validates the deployment and post-deployment setup of the TransactionManager.
contract DeployTransactionManagerTest is Test {

    //=========== State Variables for Testing ===========//
    DeployTransactionManager public deployer;
    TransactionManager public manager; // The deployed contract instance

    // These will be loaded from our .env file during the test
    address executorAdress = vm.envAddress("EXECUTOR_ADDRESS");
    uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

    //=========== Setup Function ===========//

    // This function is run before the test case.
    function setUp() public {
        // Create an instance of our deployment script.
        deployer = new DeployTransactionManager();
    }

    //=========== Deployment Test Function ===========//

    /**
     * @notice Tests the full deployment script in a simulated environment.
     * It checks:
     * 1. That the contract deploys successfully.
     * 2. That the ownership is correctly transferred to the executor address.
     */
    function test_deploymentScript() public {
        // --- 1. Pre-flight checks ---
        // Ensure that the necessary environment variables are set for the test to run.
        require(deployerPrivateKey != 0, "TEST ERROR: PRIVATE_KEY env var not set.");
        require(executorAdress != address(0), "TEST ERROR: EXECUTOR_ADDRESS env var not set.");

        // --- 2. Run the deployment script ---
        // The script returns the deployed contract instance, which we capture.
        manager = deployer.run();

        // --- 3. Post-deployment assertions ---
        // Now, we verify that the state of the deployed contract is what we expect.

        // Assertion 1: Check that the contract has a valid address (it was deployed).
        assertNotEq(address(manager), address(0), "Contract should have a valid address after deployment.");

        // Assertion 2: The MOST IMPORTANT check. Verify that the 'owner' of the
        // deployed contract is the EXECUTOR_ADDRESS we specified in our .env file.
        address currentOwner = manager.owner();
        assertEq(currentOwner, executorAdress, "Ownership was not transferred correctly.");

        // Assertion 3 (Optional but good): Check that the deployer is NO LONGER the owner.
        address deployerAddress = vm.addr(deployerPrivateKey);
        assertNotEq(currentOwner, deployerAddress, "Deployer should no longer be the owner.");
    }
}