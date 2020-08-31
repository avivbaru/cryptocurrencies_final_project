import blockchain
import utils

TRANSACTION_WAITING_TIME_BEFORE_COMPLETING = "Transactions waiting time before completing"
TRANSACTION_SUCCESSFUL = "Transactions successful"
TOTAL_CURRENT_BALANCE = "Total current balance"

BLOCKCHAIN_INSTANCE: blockchain.BlockChain = blockchain.BlockChain()
METRICS_COLLECTOR_INSTANCE: utils.MetricsCollector = utils.MetricsCollector()
FUNCTION_COLLECTOR_INSTANCE: utils.FunctionCollector = utils.FunctionCollector()
