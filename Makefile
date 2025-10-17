# Makefile for the Dynamic Transaction Optimizer project

# --- Variables ---
# Load environment variables from .env file
-include .env
export

# --- Commands ---

.PHONY: help build test coverage deploy submit

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build       Compile the smart contracts"
	@echo "  test        Run the tests"
	@echo "  coverage    Generate the test coverage report"
	@echo "  deploy      Deploy the TransactionManager contract to the network specified by SEPOLIA_RPC_URL"
	@echo "  submit      Submit a sample transaction to the TransactionManager contract"

# Compile the smart contracts
build:
	@echo "Building contracts..."
	@forge build

# Run the tests
test:
	@echo "Running tests..."
	@forge test

# Generate the test coverage report
coverage:
	@echo "Generating coverage report..."
	@forge coverage

# Deploy the TransactionManager contract
deploy:
	@echo "Deploying TransactionManager contract..."
	@forge script script/Deploy.s.sol:DeployTransactionManager --rpc-url $(SEPOLIA_RPC_URL) --private-key $(EXECUTOR_PRIVATE_KEY) --broadcast

# Submit a sample transaction to the TransactionManager contract
submit:
	@echo "Submitting a sample transaction..."
	@forge script script/SubmitTransaction.s.sol:SubmitTransaction --rpc-url $(SEPOLIA_RPC_URL) --private-key $(SUBMITTER_PRIVATE_KEY) --broadcast
