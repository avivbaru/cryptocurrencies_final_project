import blockchain
import utils

# Metrics names
TRANSACTION_WAITING_TIME_BEFORE_COMPLETING = "Transactions waiting time (in blocks) before completing avg"
TRANSACTION_SUCCESSFUL_COUNT = "Transactions successful count"
TRANSACTION_AMOUNT_AVG = "Transaction amount sent avg"
# FEE_PERCENTAGE = "Fee rate avg"
# BASE_FEE_LOG = "Base fee avg"
# CHANNEL_STARTING_BALANCE = "Starting balance of channel"
# GRIEFING_NODE_BALANCE_AVG = "Griefing node final balance avg"
# GRIEFING_SOFT_NODE_BALANCE_AVG = "Soft griefing node final balance avg"
TOTAL_LOCKED_FUND_IN_EVERY_BLOCKS = "All (summation) locked fund in every block"
# LOCKED_FUND_PER_TRANSACTION_AVG = "Locked funds (amount * duration) per applied transaction avg"
LOCKED_FUND_PER_TRANSACTION = "Locked funds per passed received transaction"
TRANSACTIONS_PASSED_THROUGH = "Transactions that passed through count"
TRANSACTIONS_PASSED_SUCCESSFUL = "Transactions passed through resolved successful count"
SEND_TRANSACTION = "Transactions tried to send count"
PATH_LENGTH_AVG = "Transaction's path length avg"
NO_PATH_FOUND = "Path not found for a transaction count"
TOTAL_FEE = "Total fee avg"
ADD_CANCELLATION_CONTRACT_FAILED = "Failed transaction - could not add cancellation contract count"
ADD_FORWARD_CONTRACT_FAILED = "Failed transaction - could not add forward contract count"
TERMINATE_TRANSACTION = "Terminated transactions count"
HONEST_NODE_BALANCE_AVG = "Honest node final balance avg"
VICTIM_NODE_BALANCE_AVG = "Victim: node final balance avg"
# ATTACKER_NODE_BALANCE_AVG = "Attacker node balance avg"
# ATTACKER_BALANCE_MINUS_VICTIM = "Attacker balance - Victim balance"

BLOCKCHAIN_INSTANCE: blockchain.BlockChain = blockchain.BlockChain()
METRICS_COLLECTOR_INSTANCE: utils.MetricsCollector = utils.MetricsCollector()
FUNCTION_COLLECTOR_INSTANCE: utils.FunctionCollector = utils.FunctionCollector()
