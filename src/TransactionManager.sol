// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title TransactionManager
 * @author Vincent Mousseaux
 * @notice This contract acts as a trusted manager for user transactions. It holds
 * transaction requests and executes them only when triggered by a trusted owner
 * (our off-chain executor service), based on optimal gas price conditions.
 */
contract TransactionManager {
    //=========== State Variables ===========//

    // The address of our off-chain executor service's wallet.
    // Only this address can call the executeTransaction function.
    address public owner;

    // A struct to hold all the necessary details for a user's transaction request.
    struct TransactionRequest {
        address submitter;      // The original user who submitted the request.
        address targetContract; // The contract the user wants to interact with.
        bytes data;             // The encoded function call and parameters (calldata).
        uint256 maxGasPrice;    // The user's maximum acceptable gas price (in Wei).
        uint256 deadline;       // A Unix timestamp after which the Tx cannot be executed.
        bool executed;          // A flag to prevent re-execution.
    }

    // A mapping to store all submitted transaction requests.
    // We use a bytes32 transaction ID as the key for efficient lookup.
    mapping(bytes32 => TransactionRequest) public transactionRequests;

    //=========== Events ===========//

    // Emitted when a new transaction is successfully submitted.
    // Our off-chain service will listen for this event.
    event TransactionSubmitted(bytes32 indexed txId, address indexed submitter, address targetContract);
    
    // Emitted when a transaction is executed.
    event TransactionExecuted(bytes32 indexed txId, bool success);

    // Emitted when a user cancels their transaction.
    event TransactionCancelled(bytes32 indexed txId);

    //=========== Modifiers ===========//

    // This is the security guard for our critical functions. It ensures
    // that only the 'owner' address can call a function.
    modifier onlyOwner() {
        _onlyOwner();
        _;
    }

    function _onlyOwner() internal view {
        require(msg.sender == owner, "Caller is not the owner");
    }

    //=========== Functions ===========//

    /**
     * @notice The constructor is called only once when the contract is deployed.
     * It sets the deployer of the contract as the initial owner.
     */
    constructor() {
        owner = msg.sender;
    }

    /**
     * @notice Allows a user to submit a transaction request to be managed.
     * @param _targetContract The address of the contract to be called.
     * @param _data The calldata for the target function call.
     * @param _maxGasPrice The maximum gas price (in Wei) the user is willing to pay.
     * @param _deadline The Unix timestamp deadline for execution.
     * @return txId A unique identifier for the transaction request.
     */
    function submitTransaction(
        address _targetContract,
        bytes calldata _data,
        uint256 _maxGasPrice,
        uint256 _deadline
    ) external returns (bytes32 txId) {
        require(_deadline > block.timestamp, "Deadline must be in the future");
        require(_targetContract != address(0), "Target contract cannot be the zero address");

        // Generate a reasonably unique ID for the transaction request.
        txId = keccak256(abi.encodePacked(msg.sender, block.timestamp, _targetContract, _data));
        
        // Store the request in our mapping.
        transactionRequests[txId] = TransactionRequest({
            submitter: msg.sender,
            targetContract: _targetContract,
            data: _data,
            maxGasPrice: _maxGasPrice,
            deadline: _deadline,
            executed: false
        });

        emit TransactionSubmitted(txId, msg.sender, _targetContract);
    }

    /**
     * @notice The core execution function, callable only by the owner (our Python script).
     * @param _txId The ID of the transaction to execute.
     */
    function executeTransaction(bytes32 _txId) external onlyOwner {
        TransactionRequest storage request = transactionRequests[_txId];

        // Perform critical security checks before execution.
        require(request.submitter != address(0), "Transaction does not exist");
        require(!request.executed, "Transaction already executed");
        require(block.timestamp <= request.deadline, "Transaction deadline has passed");
        require(tx.gasprice <= request.maxGasPrice, "Current gas price exceeds user's max");

        // Mark as executed BEFORE the external call to prevent re-entrancy attacks.
        request.executed = true;

        // Use a low-level .call() to execute the transaction.
        (bool success, ) = request.targetContract.call(request.data);

        emit TransactionExecuted(_txId, success);
    }

    /**
     * @notice Allows the original submitter to cancel their pending transaction.
     * @param _txId The ID of the transaction to cancel.
     */
    function cancelTransaction(bytes32 _txId) external {
        TransactionRequest storage request = transactionRequests[_txId];
        require(request.submitter == msg.sender, "You are not the submitter of this transaction");
        require(!request.executed, "Cannot cancel an executed transaction");
        
        // Delete the request from storage to free up space and prevent execution.
        delete transactionRequests[_txId];
        emit TransactionCancelled(_txId);
    }
    
    /**
     * @notice A critical function to transfer ownership of the contract.
     * This will be used ONE TIME after deployment to set the owner
     * to our dedicated executor wallet address.
     * @param newOwner The address of the new owner.
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "New owner cannot be the zero address");
        owner = newOwner;
    }
}