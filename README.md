# Dynamic Transaction Optimizer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

The Dynamic Transaction Optimizer is a sophisticated system designed to save users money on Ethereum transaction fees. It intelligently defers transaction execution until gas prices are favorable, using a machine learning model to predict future costs.

## Core Concept

Instead of submitting transactions directly to the Ethereum network when gas prices might be high, users submit their desired transaction to our `TransactionManager` smart contract. An off-chain "Executor" service then monitors the network and uses a predictive model to execute the transaction at the most cost-effective time, respecting a user-defined maximum price and deadline.

```
┌───────────────┐      ┌──────────────────────┐      ┌──────────────────┐
│               │      │                      │      │                  │
│   User        ├─────►│  TransactionManager  │◄─────┤  Executor        │
│ (Submitter)   │      │  (Smart Contract)    │      │  (Python Service)│
│               │      │                      │      │                  │
└───────────────┘      └──────────────────────┘      └──────────────────┘
       │                        ▲                            │
       │ 1. Submits Tx          │ 3. Executes Tx             │ 2. Monitors & Predicts
       │    (target, data,      │    when gas is low         │    best time to execute
       │    maxGas, deadline)    │                            │
       └────────────────────────┴────────────────────────────┘
```

## Features

*   **Gas Savings:** Automatically executes transactions during low-cost periods.
*   **User Control:** Users set a maximum acceptable gas price (`maxGasPrice`) and an execution deadline.
*   **Predictive Execution:** Utilizes a pre-trained machine learning model to forecast gas prices and make intelligent execution decisions.
*   **Secure & Non-Custodial:** The `TransactionManager` contract holds the transaction data, and the user-provided private keys are only used locally for signing.
*   **Event-Driven:** The system is built on an event-driven architecture, with the executor listening for `TransactionSubmitted` events.

## Project Structure

```
.
├── Makefile              # Convenient commands for building, testing, and deploying
├── foundry.toml          # Foundry configuration
├── ml/                   # Python-based executor and ML model
│   ├── executor.py       # The core off-chain service
│   ├── gas_predictor.pkl # The pre-trained gas prediction model
│   └── ...
├── script/               # Solidity scripts for deployment and interaction
│   ├── Deploy.s.sol      # Deploys the TransactionManager
│   └── SubmitTransaction.s.sol # Submits a sample transaction
├── src/                  # Core smart contracts
│   └── TransactionManager.sol
└── test/                 # Foundry tests for the smart contracts
```

## Getting Started

### Prerequisites

*   [Foundry](https://book.getfoundry.sh/getting-started/installation): For smart contract development, testing, and deployment.
*   [Python](https://www.python.org/downloads/) (3.8+) and `pip`.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/dynamic-transaction-optimizer.git
    cd dynamic-transaction-optimizer
    ```

2.  **Install smart contract dependencies:**
    ```bash
    forge install
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install -r ml/requirements.txt
    ```

### Configuration

The project uses a `.env` file to manage secret keys and configuration.

1.  **Create the `.env` file:**
    ```bash
    cp .env.example .env
    ```

2.  **Edit the `.env` file:**
    You will need two separate Ethereum accounts (e.g., from Metamask) for a full end-to-end test:
    *   **Executor Account:** Deploys the contract and executes transactions.
    *   **Submitter Account:** Submits transaction requests.

    Fill in the details in your `.env` file:
    ```
    # .env file for Dynamic Transaction Optimizer

    # -- Blockchain Connection --
    # Use a local Anvil node for testing.
    SEPOLIA_RPC_URL=http://127.0.0.1:8545

    # -- Executor Account (from Metamask) --
    EXECUTOR_PRIVATE_KEY=<YOUR_EXECUTOR_ACCOUNT_PRIVATE_KEY>
    EXECUTOR_ADDRESS=<YOUR_EXECUTOR_ACCOUNT_ADDRESS>

    # -- Submitter Account (from Metamask) --
    SUBMITTER_PRIVATE_KEY=<YOUR_SUBMITTER_ACCOUNT_PRIVATE_KEY>

    # -- Contract Addresses (will be updated after deployment) --
    CONTRACT_ADDRESS=
    TARGET_CONTRACT_ADDRESS=
    ```
    > **Security Warning:** Never commit your `.env` file to version control. It contains private keys.

## Usage (End-to-End Test)

This guide walks you through running the entire system on a local Anvil node.

**1. Start a Local Blockchain**
Open a new terminal and run:
```bash
anvil
```
This will start a local Ethereum node and provide you with 10 test accounts.

**2. Deploy the Contracts**
In another terminal, run the `deploy` command. This will deploy the `TransactionManager` contract using your Executor Account.
```bash
make deploy
```
The command will output the address of the deployed `TransactionManager`. **Copy this address and paste it into the `CONTRACT_ADDRESS` field in your `.env` file.**

**3. Deploy a Target Contract**
For this example, we need a contract to interact with. A sample `Counter.sol` is included. Deploy it by running:
```bash
forge script script/DeployCounter.s.sol --rpc-url $(SEPOLIA_RPC_URL) --private-key $(EXECUTOR_PRIVATE_KEY) --broadcast
```
This will output the address of the `Counter` contract. **Copy this address and paste it into the `TARGET_CONTRACT_ADDRESS` field in your `.env` file.**

**4. Start the Executor Service**
The executor is the brain of the operation. Start it by running:
```bash
python ml/executor.py
```
The service will start, connect to the blockchain, and begin monitoring for transactions.

**5. Submit a Transaction**
With everything running, you can now submit a transaction from your Submitter Account. Open a third terminal and run:
```bash
make submit
```
This command executes the `SubmitTransaction.s.sol` script, which submits a request to call the `increment()` function on the `Counter` contract.

**6. Observe the System in Action**
Watch the output in your executor terminal. You will see:
1.  The executor detects the `TransactionSubmitted` event.
2.  It starts its decision logic, comparing the current gas price to the model's prediction and your `maxGasPrice`.
3.  Once the conditions are met, it will broadcast the transaction.
4.  You will see a "SUCCESS" message when the transaction is executed on-chain.

## Makefile Commands

The `Makefile` provides several useful commands:
*   `make build`: Compiles the smart contracts.
*   `make test`: Runs the Foundry test suite.
*   `make deploy`: Deploys the `TransactionManager` contract.
*   `make submit`: Submits a sample transaction to the `TransactionManager`.
*   `make coverage`: Generates a test coverage report.

## Future Improvements

*   **Frontend Interface:** A simple dApp to allow users to easily submit transactions and view their status.
*   **Advanced ML Model:** Retrain the model with more features and data for even more accurate gas price predictions.
*   **Multi-Chain Support:** Adapt the system to work with other EVM-compatible chains.
*   **Gas Estimation for Submission:** Provide users with a gas estimate for the final execution at the time of submission.