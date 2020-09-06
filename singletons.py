import blockchain
import utils

# Metrics names
TRANSACTION_WAITING_TIME_BEFORE_COMPLETING = "Transactions waiting time (in blocks) before completing avg"
TRANSACTION_SUCCESSFUL_COUNT = "Transactions successful"
TRANSACTION_AMOUNT_AVG = "Transaction amount sent avg"
# FEE_PERCENTAGE = "Fee rate avg"
# BASE_FEE_LOG = "Base fee avg"
# CHANNEL_STARTING_BALANCE = "Starting balance of channel"
# HONEST_NODE_BALANCE_AVG = "Honest node final balance avg"
# GRIEFING_NODE_BALANCE_AVG = "Griefing node final balance avg"
# GRIEFING_SOFT_NODE_BALANCE_AVG = "Soft griefing node final balance avg"
TOTAL_LOCKED_FUND_IN_EVERY_BLOCKS = "All (summation) locked fund in every block"
LOCKED_FUND_PER_TRANSACTION_AVG = "Locked funds (amount * duration) per successful transaction avg"
LOCKED_FUND_PER_TRANSACTION_NORMALIZE_BY_AMOUNT_SENT_AVG = "Locked fund (amount * duration) per successful transaction " \
                                                           "(normalize by amount sent) avg"
DURATION_OF_LOCKED_FUNDS_IN_BLOCKS = "Duration (in blocks) of Locked funds avg"  # TODO: this is a weird metric
SEND_TRANSACTION = "Transactions tried to send"
PATH_LENGTH_AVG = "Transactions path length avg"
NO_PATH_FOUND = "Amount of path not found for a transaction"
TOTAL_FEE = "Total fee avg"
PERFORM_SOFT_GRIEFING = "Perform soft griefing"
ADD_CANCELLATION_CONTRACT_FAILED = "Fail transaction - could not add cancellation contract"
ADD_FORWARD_CONTRACT_FAILED = "Fail transaction - could not add forward contract"
DELAYED_RUN_FUNCTION = "Delayed run function"
DELAYED_RUN_FUNCTION_AVG = "Number of blocks to delayed function run avg"
TERMINATE_TRANSACTION = "Terminate transaction"
# VICTIM_NODE_BALANCE_AVG = "Victim node balance avg"
# ATTACKER_NODE_BALANCE_AVG = "Attacker node balance avg"
# ATTACKER_BALANCE_MINUS_VICTIM = "Attacker balance - Victim balance"
TRANSACTIONS_PASSED_SUCCESSFUL = "Transactions passed through resolved successful"

BLOCKCHAIN_INSTANCE: blockchain.BlockChain = blockchain.BlockChain()
METRICS_COLLECTOR_INSTANCE: utils.MetricsCollector = utils.MetricsCollector()
FUNCTION_COLLECTOR_INSTANCE: utils.FunctionCollector = utils.FunctionCollector()
