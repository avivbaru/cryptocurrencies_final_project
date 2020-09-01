import blockchain
import utils

# Metrics names
TRANSACTION_WAITING_TIME_BEFORE_COMPLETING = "Transactions waiting time before completing"
TRANSACTION_SUCCESSFUL = "Transactions successful"
TOTAL_CURRENT_BALANCE = "Total current balance"
TRANSACTION_AMOUNT = "Transaction amount"
FEE_PERCENTAGE = "Fee percentage"
BASE_FEE_LOG = "Base fee"
CHANNEL_STARTING_BALANCE = "Channel starting balance"
HONEST_NODE_BALANCE_AVG = "Honest node balance"
GRIEFING_NODE_BALANCE_AVG = "Griefing node balance"
GRIEFING_SOFT_NODE_BALANCE_AVG = "Soft griefing node balance"
BLOCK_LOCKED_FUND = "Block locked fund"
TOTAL_LOCKED_FUND_IN_EVERY_BLOCKS = "Total locked fund in every blocks"
# TOTAL_LOCKED_FUND = "Total locked fund"
SEND_TRANSACTION = "Send Transaction"
PATH_LENGTH_AVG = "Path length"
NO_PATH_FOUND = "No path found"
SEND_FAILED = "Send failed"

BLOCKCHAIN_INSTANCE: blockchain.BlockChain = blockchain.BlockChain()
METRICS_COLLECTOR_INSTANCE: utils.MetricsCollector = utils.MetricsCollector()
FUNCTION_COLLECTOR_INSTANCE: utils.FunctionCollector = utils.FunctionCollector()
