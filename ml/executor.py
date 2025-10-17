import os
import time
import json
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
EXECUTOR_PRIVATE_KEY = os.getenv("EXECUTOR_PRIVATE_KEY") 
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

# --- Constants ---
ABI_FILE_PATH = "../out/TransactionManager.sol/TransactionManager.json"
PERSISTENCE_FILE = "tracked_transactions.json"
DEADLINE_THRESHOLD_SECONDS = 900 # 15 minutes

def load_abi(file_path):
    """Loads the ABI from a JSON file."""
    with open(file_path, 'r') as f:
        data = json.load(f)
        return data['abi']

CONTRACT_ABI = load_abi(ABI_FILE_PATH)

# Check for missing configuration
if not all([SEPOLIA_RPC_URL, EXECUTOR_PRIVATE_KEY, CONTRACT_ADDRESS]):
    raise ValueError("Missing critical environment variables or contract address.")

# --- 2. SETUP (Connect to Blockchain and Load Model) ---
# -------------------------------------------------------
print("Connecting to Sepolia network...")
w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL))
if not w3.is_connected():
    raise ConnectionError("Failed to connect to the Ethereum node.")

executor_account = w3.eth.account.from_key(EXECUTOR_PRIVATE_KEY)
print(f"Executor account address: {executor_account.address}")

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

print("Loading gas prediction model...")
model = joblib.load('gas_predictor.pkl')
print("Setup complete. Model and contract loaded.")

# --- Persistence Functions ---
def save_tracked_transactions(transactions):
    """Saves the tracked transactions to a file."""
    # Convert bytes to hex for JSON serialization
    serializable_txs = {tx_id.hex(): tx_info for tx_id, tx_info in transactions.items()}
    with open(PERSISTENCE_FILE, 'w') as f:
        json.dump(serializable_txs, f, indent=4)

def load_tracked_transactions():
    """Loads tracked transactions from a file."""
    if not os.path.exists(PERSISTENCE_FILE):
        return {}
    with open(PERSISTENCE_FILE, 'r') as f:
        serializable_txs = json.load(f)
        # Convert hex back to bytes
        return {bytes.fromhex(tx_id): tx_info for tx_id, tx_info in serializable_txs.items()}

# --- 3. CORE ORACLE FUNCTIONS ---
# --------------------------------

def get_live_features():
    """Fetches live data from the blockchain for the model."""
    try:
        latest_block = w3.eth.get_block('latest')
        current_gas_gwei = latest_block.base_fee_per_gas / 1e9
        now = pd.Timestamp.now(tz='UTC')
        
        # In a production system, you would query historical data.
        # For this example, we continue to use placeholders.
        feature_df = pd.DataFrame([{
            'avg_gas_in_gwei': current_gas_gwei,
            'hour_of_day': float(now.hour),
            'day_of_week': float(now.dayofweek),
            'month': float(now.month),
            'rolling_avg_24h': current_gas_gwei, 
            'lag_1h': current_gas_gwei
        }])
        return feature_df, current_gas_gwei
    except Exception as e:
        print(f"Error fetching live features: {e}")
        return None, None

def make_decision(tx_request):
    """Uses the ML model and deadline to decide whether to execute."""
    features, current_gas = get_live_features()
    if features is None:
        return False

    predicted_gas = model.predict(features)[0]
    user_max_gas = tx_request['maxGasPrice'] / 1e9
    deadline = tx_request['deadline']
    
    print(f"Decision logic for TxID {tx_request['txId'].hex()[:10]}... | "
          f"Current Gas: {current_gas:.2f} | Predicted: {predicted_gas:.2f} | "
          f"User Max: {user_max_gas:.2f} | Deadline in: {(deadline - time.time())/60:.1f} mins")

    is_below_max = current_gas < user_max_gas
    is_good_time = current_gas < (predicted_gas * 1.05)
    is_urgent = (deadline - time.time()) < DEADLINE_THRESHOLD_SECONDS

    if not is_below_max:
        print("DECISION: Wait. Current gas is above user's max.")
        return False

    if is_urgent:
        print("DECISION: Execute. Transaction is urgent.")
        return True

    if is_good_time:
        print("DECISION: Execute. Gas price is favorable.")
        return True
    else:
        print("DECISION: Wait for a better time.")
        return False

def execute_transaction_on_chain(tx_id):
    """Builds, signs, and sends the transaction with refined gas estimation."""
    try:
        print(f"Building transaction to execute TxID {tx_id.hex()[:10]}...")
        
        # Refined Gas Estimation
        gas_estimate = contract.functions.executeTransaction(tx_id).estimate_gas({
            'from': executor_account.address
        })
        gas_limit = int(gas_estimate * 1.2) # Add a 20% buffer

        tx_call = contract.functions.executeTransaction(tx_id).build_transaction({
            'from': executor_account.address,
            'nonce': w3.eth.get_transaction_count(executor_account.address),
            'gas': gas_limit,
            'maxFeePerGas': w3.eth.get_block('latest')['baseFeePerGas'] + w3.to_wei(2, 'gwei'),
            'maxPriorityFeePerGas': w3.to_wei(2, 'gwei'),
        })

        signed_tx = w3.eth.account.sign_transaction(tx_call, private_key=EXECUTOR_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        print(f"Transaction sent! Hash: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt.status == 1:
            print(f"SUCCESS: Transaction {tx_id.hex()[:10]}... executed successfully.")
            return True
        else:
            print(f"FAIL: Transaction {tx_id.hex()[:10]}... execution failed on-chain.")
            return False

    except Exception as e:
        print(f"An error occurred during on-chain execution: {e}")
        return False

# --- 4. MAIN EVENT LOOP ---
# --------------------------

def main_loop():
    print("\n--- Starting Main Oracle Loop ---")
    tracked_transactions = load_tracked_transactions()
    print(f"Loaded {len(tracked_transactions)} transactions from persistence file.")
    
    event_filter = contract.events.TransactionSubmitted.create_filter(from_block="latest")

    while True:
        for event in event_filter.get_new_entries():
            tx_id = event['args']['txId']
            if tx_id not in tracked_transactions:
                print(f"New transaction submitted: {tx_id.hex()}")
                # We need the full transaction details for the decision logic
                (submitter, target, data, max_gas, deadline, executed) = \
                    contract.functions.transactionRequests(tx_id).call()
                tracked_transactions[tx_id] = {
                    "txId": tx_id,
                    "maxGasPrice": max_gas,
                    "deadline": deadline
                }
                save_tracked_transactions(tracked_transactions)

        for tx_id, tx_info in list(tracked_transactions.items()):
            try:
                (submitter, _, _, _, _, executed) = contract.functions.transactionRequests(tx_id).call()

                if submitter != '0x0000000000000000000000000000000000000000' and not executed:
                    if make_decision(tx_info):
                        if execute_transaction_on_chain(tx_id):
                            del tracked_transactions[tx_id]
                            save_tracked_transactions(tracked_transactions)
                            print(f"Transaction {tx_id.hex()} processed and removed.")
                else:
                    print(f"Transaction {tx_id.hex()[:10]}... is old. Removing.")
                    del tracked_transactions[tx_id]
                    save_tracked_transactions(tracked_transactions)

            except Exception as e:
                 print(f"An error occurred in the main loop for tx {tx_id.hex()}: {e}")

        print(f"Sleeping for 15 seconds... Tracking {len(tracked_transactions)} transactions.")
        time.sleep(15)

if __name__ == "__main__":
    main_loop()