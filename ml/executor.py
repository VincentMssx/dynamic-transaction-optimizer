import os
import time
import pandas as pd
import joblib
from web3 import Web3
from dotenv import load_dotenv

# --- 1. CONFIGURATION ---
# ------------------------
print("Starting Executor Service...")
load_dotenv('../.env') # Load variables from the root .env file

# Load environment variables
SEPOLIA_RPC_URL = os.getenv("SEPOLIA_RPC_URL")
# IMPORTANT: This must be the private key for the EXECUTOR_ADDRESS set in your .env
EXECUTOR_PRIVATE_KEY = os.getenv("EXECUTOR_PRIVATE_KEY") 

# Contract details - UPDATE THESE AFTER DEPLOYMENT
# The address of your deployed TransactionManager contract
CONTRACT_ADDRESS = "0xYourDeployedContractAddressGoesHere" 
# Paste the ABI array from out/TransactionManager.sol/TransactionManager.json here
CONTRACT_ABI = """
[
{"type":"constructor","inputs":[],"stateMutability":"nonpayable"},{"type":"function","name":"cancelTransaction","inputs":[{"name":"_txId","type":"bytes32","internalType":"bytes32"}],"outputs":[],"stateMutability":"nonpayable"},{"type":"function","name":"executeTransaction","inputs":[{"name":"_txId","type":"bytes32","internalType":"bytes32"}],"outputs":[],"stateMutability":"nonpayable"},{"type":"function","name":"owner","inputs":[],"outputs":[{"name":"","type":"address","internalType":"address"}],"stateMutability":"view"},{"type":"function","name":"submitTransaction","inputs":[{"name":"_targetContract","type":"address","internalType":"address"},{"name":"_data","type":"bytes","internalType":"bytes"},{"name":"_maxGasPrice","type":"uint256","internalType":"uint256"},{"name":"_deadline","type":"uint256","internalType":"uint256"}],"outputs":[{"name":"txId","type":"bytes32","internalType":"bytes32"}],"stateMutability":"nonpayable"},{"type":"function","name":"transactionRequests","inputs":[{"name":"","type":"bytes32","internalType":"bytes32"}],"outputs":[{"name":"submitter","type":"address","internalType":"address"},{"name":"targetContract","type":"address","internalType":"address"},{"name":"data","type":"bytes","internalType":"bytes"},{"name":"maxGasPrice","type":"uint256","internalType":"uint256"},{"name":"deadline","type":"uint256","internalType":"uint256"},{"name":"executed","type":"bool","internalType":"bool"}],"stateMutability":"view"},{"type":"function","name":"transferOwnership","inputs":[{"name":"newOwner","type":"address","internalType":"address"}],"outputs":[],"stateMutability":"nonpayable"},{"type":"event","name":"TransactionCancelled","inputs":[{"name":"txId","type":"bytes32","indexed":true,"internalType":"bytes32"}],"anonymous":false},{"type":"event","name":"TransactionExecuted","inputs":[{"name":"txId","type":"bytes32","indexed":true,"internalType":"bytes32"},{"name":"success","type":"bool","indexed":false,"internalType":"bool"}],"anonymous":false},{"type":"event","name":"TransactionSubmitted","inputs":[{"name":"txId","type":"bytes32","indexed":true,"internalType":"bytes32"},{"name":"submitter","type":"address","indexed":true,"internalType":"address"},{"name":"targetContract","type":"address","indexed":false,"internalType":"address"}],"anonymous":false}
]
"""

# Check for missing configuration
if not all([SEPOLIA_RPC_URL, EXECUTOR_PRIVATE_KEY, CONTRACT_ADDRESS]):
    raise ValueError("Missing critical environment variables or contract address.")

# --- 2. SETUP (Connect to Blockchain and Load Model) ---
# -------------------------------------------------------
print("Connecting to Sepolia network...")
w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL))
if not w3.is_connected():
    raise ConnectionError("Failed to connect to the Ethereum node.")

# Set up the executor account from its private key
executor_account = w3.eth.account.from_key(EXECUTOR_PRIVATE_KEY)
# Verify the address matches the one you set as owner
print(f"Executor account address: {executor_account.address}")

# Load the smart contract instance
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

# Load the trained machine learning model
print("Loading gas prediction model...")
model = joblib.load('gas_predictor.pkl')
print("Setup complete. Model and contract loaded.")

# A simple in-memory store for transactions we are tracking
# In a production system, you would use a database for this.
tracked_transactions = {}

# --- 3. CORE ORACLE FUNCTIONS ---
# --------------------------------

def get_live_features():
    """
    Fetches live data from the blockchain and engineers the features
    required by our trained model.
    """
    try:
        latest_block = w3.eth.get_block('latest')
        
        # Current gas price (base fee)
        current_gas_gwei = latest_block.base_fee_per_gas / 1e9
        
        # Time-based features
        now = pd.Timestamp.now(tz='UTC')
        hour_of_day = now.hour
        day_of_week = now.dayofweek
        month = now.month
        
        # NOTE: For rolling_avg and lag features, a real production system would
        # query the last 24 hours of blocks. For this example, we'll use a simplified
        # placeholder. We'll use the current price as a stand-in for these features.
        rolling_avg_24h = current_gas_gwei 
        lag_1h = current_gas_gwei

        # Create a DataFrame in the exact format the model was trained on
        feature_df = pd.DataFrame([{
            'avg_gas_in_gwei': current_gas_gwei,
            'hour_of_day': float(hour_of_day),
            'day_of_week': float(day_of_week),
            'month': float(month),
            'rolling_avg_24h': rolling_avg_24h,
            'lag_1h': lag_1h
        }])
        
        return feature_df, current_gas_gwei
    except Exception as e:
        print(f"Error fetching live features: {e}")
        return None, None

def make_decision(tx_request):
    """
    Uses the ML model to predict future gas price and decides whether to execute.
    """
    features, current_gas = get_live_features()
    if features is None:
        return False # Don't execute if we can't get data

    # Use the model to predict the gas price in the next hour
    predicted_gas = model.predict(features)[0]
    
    user_max_gas = tx_request['maxGasPrice'] / 1e9 # Convert from Wei to Gwei
    
    print(f"Decision logic for TxID {tx_request['txId'][:10]}... | "
          f"Current Gas: {current_gas:.2f} Gwei | "
          f"Predicted Gas: {predicted_gas:.2f} Gwei | "
          f"User Max: {user_max_gas:.2f} Gwei")

    # --- THE CORE DECISION LOGIC ---
    # 1. The current price must be below the user's maximum.
    is_below_max = current_gas < user_max_gas
    # 2. We execute if the current price is good AND we predict it will rise.
    is_good_time = current_gas < (predicted_gas * 1.05) # Execute if current price is lower than predicted
    
    if is_below_max and is_good_time:
        print("DECISION: Execute transaction.")
        return True
    else:
        print("DECISION: Wait for a better time.")
        return False

def execute_transaction_on_chain(tx_id):
    """
    Builds, signs, and sends the transaction to call 'executeTransaction' on the contract.
    """
    try:
        print(f"Building transaction to execute TxID {tx_id[:10]}...")
        
        # Build the transaction object
        tx_call = contract.functions.executeTransaction(tx_id).build_transaction({
            'from': executor_account.address,
            'nonce': w3.eth.get_transaction_count(executor_account.address),
            'gas': 200000, # Set a reasonable gas limit
            # Use the latest base fee + a 2 Gwei priority fee for faster inclusion
            'maxFeePerGas': w3.eth.get_block('latest')['baseFeePerGas'] + w3.to_wei(2, 'gwei'),
            'maxPriorityFeePerGas': w3.to_wei(2, 'gwei'),
        })

        signed_tx = w3.eth.account.sign_transaction(tx_call, private_key=EXECUTOR_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        print(f"Transaction sent! Hash: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt.status == 1:
            print(f"SUCCESS: Transaction {tx_id[:10]}... executed successfully.")
            return True
        else:
            print(f"FAIL: Transaction {tx_id[:10]}... execution failed on-chain.")
            return False

    except Exception as e:
        print(f"An error occurred during on-chain execution: {e}")
        return False

# --- 4. MAIN EVENT LOOP ---
# --------------------------

def main_loop():
    print("\n--- Starting Main Oracle Loop ---")
    # In a real app, you would listen for 'TransactionSubmitted' events.
    # To keep this example simple, we will manually check a transaction.
    # We will simulate that we "heard" an event and have a txId to track.
    
    # TODO: Replace with a real event listener and a database of txIds.
    # For now, we will need to get a txId by submitting a transaction manually
    # and pasting the txId here.
    
    # EXAMPLE: manually_tracked_tx_id = "0xc4f55d33df64ffba4af52153eec2ef3af93a2c7ac5aabaf2d401b7f142100c76"
    manually_tracked_tx_id = None # Set this to a real TxID to test

    if not manually_tracked_tx_id:
        print("\nWARNING: No transaction to track. Please submit a transaction to the contract" \
              " and paste its 'txId' into the 'manually_tracked_tx_id' variable.")

    while True:
        if manually_tracked_tx_id:
            try:
                # Get the latest details of the transaction from the contract
                (submitter, target, data, max_gas, deadline, executed) = \
                    contract.functions.transactionRequests(manually_tracked_tx_id).call()

                if submitter != '0x0000000000000000000000000000000000000000' and not executed:
                    tx_request = {
                        "txId": manually_tracked_tx_id,
                        "maxGasPrice": max_gas
                    }
                    if make_decision(tx_request):
                        if execute_transaction_on_chain(manually_tracked_tx_id):
                            # Stop tracking after successful execution
                             manually_tracked_tx_id = None
                             print("Transaction processed. Halting loop for this example.")
                             break 
                else:
                    print(f"Transaction {manually_tracked_tx_id[:10]}... is already executed or cancelled. Halting.")
                    break
            except Exception as e:
                 print(f"An error occurred in the main loop: {e}")

        # Wait for 60 seconds before the next check
        print("Sleeping for 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    main_loop()