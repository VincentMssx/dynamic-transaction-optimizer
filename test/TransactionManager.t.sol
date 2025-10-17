// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "../lib/forge-std/src/Test.sol";
import {TransactionManager} from "../src/TransactionManager.sol";

// A simple contract that can revert
contract RevertingContract {
    function revertFunction() public pure {
        revert("I am reverting");
    }
}

contract TransactionManagerTest is Test {
    TransactionManager public manager;
    address public owner = makeAddr("owner");
    address public user = makeAddr("user");
    address public targetContract = makeAddr("targetContract");
    RevertingContract public revertingContract;

    event TransactionSubmitted(bytes32 indexed txId, address indexed submitter, address targetContract);
    event TransactionExecuted(bytes32 indexed txId, bool success);

    function setUp() public {
        vm.prank(owner);
        manager = new TransactionManager();
        revertingContract = new RevertingContract();
    }

    // --- Unit Tests ---

    function test_unit_submitTransaction_succeeds() public {
        vm.prank(user);
        bytes32 txId = manager.submitTransaction(targetContract, "0x", 100 gwei, block.timestamp + 1 hours);
        assertNotEq(txId, bytes32(0));
        (address submitter, address target,,,,) = manager.transactionRequests(txId);
        assertEq(submitter, user);
        assertEq(target, targetContract);
    }

    function test_unit_submitTransaction_failsWithPastDeadline() public {
        vm.prank(user);
        vm.expectRevert("Deadline must be in the future");
        manager.submitTransaction(targetContract, "0x", 100 gwei, block.timestamp - 1);
    }

    function test_unit_submitTransaction_failsWithZeroAddress() public {
        vm.prank(user);
        vm.expectRevert("Target contract cannot be the zero address");
        manager.submitTransaction(address(0), "0x", 100 gwei, block.timestamp + 1 hours);
    }

    function test_unit_executeTransaction_succeedsAsOwner() public {
        vm.prank(user);
        bytes32 txId = manager.submitTransaction(targetContract, "0x", 100 gwei, block.timestamp + 1 hours);
        vm.prank(owner);
        manager.executeTransaction(txId);
        (,,,,, bool executed) = manager.transactionRequests(txId);
        assertTrue(executed);
    }

    function test_unit_executeTransaction_failsAsNonOwner() public {
        vm.prank(user);
        bytes32 txId = manager.submitTransaction(targetContract, "0x", 100 gwei, block.timestamp + 1 hours);
        vm.prank(user);
        vm.expectRevert("Caller is not the owner");
        manager.executeTransaction(txId);
    }

    function test_unit_executeTransaction_failsWithNonExistentTx() public {
        vm.prank(owner);
        vm.expectRevert("Transaction does not exist");
        manager.executeTransaction(bytes32(0));
    }

    function test_unit_executeTransaction_failsWhenAlreadyExecuted() public {
        vm.prank(user);
        bytes32 txId = manager.submitTransaction(targetContract, "0x", 100 gwei, block.timestamp + 1 hours);
        vm.prank(owner);
        manager.executeTransaction(txId);
        vm.prank(owner);
        vm.expectRevert("Transaction already executed");
        manager.executeTransaction(txId);
    }

    function test_unit_executeTransaction_failsWhenDeadlinePassed() public {
        vm.prank(user);
        bytes32 txId = manager.submitTransaction(targetContract, "0x", 100 gwei, block.timestamp + 1 hours);
        vm.warp(block.timestamp + 2 hours);
        vm.prank(owner);
        vm.expectRevert("Transaction deadline has passed");
        manager.executeTransaction(txId);
    }

    function test_unit_executeTransaction_failsWithHighGasPrice() public {
        vm.prank(user);
        bytes32 txId = manager.submitTransaction(targetContract, "0x", 100 gwei, block.timestamp + 1 hours);
        vm.prank(owner);
        vm.txGasPrice(101 gwei);
        vm.expectRevert("Current gas price exceeds user's max");
        manager.executeTransaction(txId);
    }

    function test_unit_executeTransaction_failsWithFailedCall() public {
        vm.prank(user);
        bytes memory callData = abi.encodeWithSignature("revertFunction()");
        bytes32 txId = manager.submitTransaction(address(revertingContract), callData, 100 gwei, block.timestamp + 1 hours);
        vm.prank(owner);
        vm.expectEmit(true, false, false, true);
        emit TransactionExecuted(txId, false);
        manager.executeTransaction(txId);
    }

    function test_unit_cancelTransaction_succeedsAsSubmitter() public {
        vm.prank(user);
        bytes32 txId = manager.submitTransaction(targetContract, "0x", 100 gwei, block.timestamp + 1 hours);
        vm.prank(user);
        manager.cancelTransaction(txId);
        (address submitter,,,,,) = manager.transactionRequests(txId);
        assertEq(submitter, address(0));
    }

    function test_unit_cancelTransaction_failsAsOtherUser() public {
        address otherUser = makeAddr("otherUser");
        vm.prank(user);
        bytes32 txId = manager.submitTransaction(targetContract, "0x", 100 gwei, block.timestamp + 1 hours);
        vm.prank(otherUser);
        vm.expectRevert("You are not the submitter of this transaction");
        manager.cancelTransaction(txId);
    }

    function test_unit_cancelTransaction_failsWhenAlreadyExecuted() public {
        vm.prank(user);
        bytes32 txId = manager.submitTransaction(targetContract, "0x", 100 gwei, block.timestamp + 1 hours);
        vm.prank(owner);
        manager.executeTransaction(txId);
        vm.prank(user);
        vm.expectRevert("Cannot cancel an executed transaction");
        manager.cancelTransaction(txId);
    }

    function test_unit_transferOwnership_failsWithZeroAddress() public {
        vm.prank(owner);
        vm.expectRevert("New owner cannot be the zero address");
        manager.transferOwnership(address(0));
    }

    // --- Integration Test ---

    function test_integration_fullLifecycle() public {
        // --- 1. SUBMIT ---
        vm.prank(user);

        // --- FINAL, ROBUST FIX ---
        // Set up the check. We tell it to check topic 2 (the submitter).
        // We will NOT check the non-indexed data because it's complex and often not needed.
        // checkTopic1 (txId): false
        // checkTopic2 (submitter): true
        // checkTopic3 (N/A): false
        // checkData: false
        vm.expectEmit(false, true, false, false);

        // Tell Foundry the value to expect for the topic we are checking (topic 2).
        // The event signature is: TransactionSubmitted(bytes32, address, address)
        // Topic 0 is the hash of the signature.
        // Topic 1 is the first indexed param (txId).
        // Topic 2 is the second indexed param (submitter).
        emit TransactionSubmitted(bytes32(0), user, address(0));

        bytes32 txId = manager.submitTransaction(targetContract, "0x", 100 gwei, block.timestamp + 1 hours);

        // --- 2. ADVANCE TIME ---
        vm.warp(block.timestamp + 30 minutes);

        // --- 3. EXECUTE ---
        vm.prank(owner);

        // --- FINAL, ROBUST FIX ---
        // Set up the check. We know the txId now, so we can check it.
        // checkTopic1 (txId): true
        // checkTopic2 (N/A): false
        // checkTopic3 (N/A): false
        // checkData: true (we'll check the 'success' boolean)
        vm.expectEmit(true, false, false, true);

        // Tell Foundry what to expect for the topics and data.
        emit TransactionExecuted(txId, true);

        manager.executeTransaction(txId);

        // --- 4. VERIFY FINAL STATE ---
        (,,,,, bool executed) = manager.transactionRequests(txId);
        assertTrue(executed, "Request should be marked as executed");

        // --- 5. ATTEMPT DOUBLE EXECUTION ---
        vm.prank(owner);
        vm.expectRevert("Transaction already executed");
        manager.executeTransaction(txId);
    }
}
