import random
import time
import math
import fire
import json
import inspect
import lightning_node
from datetime import datetime
from network import Network
from singletons import METRICS_COLLECTOR_INSTANCE, FUNCTION_COLLECTOR_INSTANCE, BLOCKCHAIN_INSTANCE

# metrics names
HONEST_NODE_BALANCE_AVG = "honest_node_balance"
GRIEFING_NODE_BALANCE_AVG = "griefing_node_balance"
GRIEFING_SOFT_NODE_BALANCE_AVG = "soft_griefing_node_balance"
BLOCK_LOCKED_FUND = "block_locked_fund"
SEND_SUCCESSFULLY = "send_successfully"
PATH_LENGTH_AVG = "path_length"
NO_PATH_FOUND = "no_path_found"
SEND_FAILED = "send_failed"

# parameters ofr runs
MIN_TO_SEND = 100
MAX_TO_SEND = 1000000000
MSAT_AMOUNTS_TO_SEND = [1000, 10000, 100000, 1000000, 10000000, 100000000]
MSAT_CHANNEL_CAPACITY = [500000000, 1000000000, 1500000000, 2000000000, 2500000000, 3000000000, 3500000000,
                         4000000000, 4500000000, 5000000000, 5500000000, 6000000000, 6500000000,
                         7500000000, 8500000000, 9500000000, 10000000000, 10500000000, 15500000000,
                         16500000000, 17000000000]
MSAT_CHANNEL_CAPACITY_PROB = [0.477, 0.110, 0.109, 0.019, 0.051, 0.013, 0.023, 0.005, 0.015, 0.007, 0.044,
                              0.003, 0.006, 0.003, 0.015, 0.009, 0.002, 0.024, 0.005, 0.009, 0.052]
BASE_FEE = [0, 100, 200, 300, 400, 500, 600, 800, 900, 1000, 2000, 3000, 5000, 10000]
BASE_FEE_PROB = [0.300, 0.019, 0.003, 0.005, 0.019, 0.011, 0.002, 0.011, 0.012, 0.591, 0.005, 0.008, 0.007,
                 0.007]
FEE_RATE = [0, 1, 2, 3, 5, 9, 10, 15, 19, 20, 25, 30, 40, 42, 45, 50, 56, 70, 80, 90, 100, 101, 120, 200, 250,
            400, 488, 489, 500, 560, 800, 999, 1000, 1250, 2000, 2500, 3000, 5000, 1000000]
FEE_RATE_PROB = [0.066, 0.597, 0.007, 0.002, 0.006, 0.002, 0.046, 0.002, 0.004, 0.002, 0.002, 0.002, 0.002,
                 0.005, 0.001, 0.005, 0.007, 0.001, 0.001, 0.004, 0.029, 0.005, 0.003, 0.054, 0.003, 0.020,
                 0.002, 0.001, 0.012, 0.003, 0.041, 0.003, 0.022, 0.002, 0.005, 0.021, 0.002, 0.007, 0.002]
STARTING_BALANCE = 17000000000 * 1000  # so the node have enough balance to create all channels
GRIEFING_PENALTY_RATE = 0.001
HTLCS_PER_BLOCK = 20
SIGMA = 0.1


def how_much_to_send():
    mu = random.choice(MSAT_AMOUNTS_TO_SEND)
    return int(min(max(random.gauss(mu, SIGMA), MIN_TO_SEND), MAX_TO_SEND))


def create_node(is_soft_griefing=False):
    # divide by million to get the rate per msat
    fee_percentage = random.choices(FEE_RATE, weights=FEE_RATE_PROB, k=1)[0] / 1000000
    base_fee = random.choices(BASE_FEE, weights=BASE_FEE_PROB, k=1)[0]
    if is_soft_griefing:
        return lightning_node.LightningNodeSoftGriefing(STARTING_BALANCE, base_fee, fee_percentage, GRIEFING_PENALTY_RATE)
    return lightning_node.LightningNode(STARTING_BALANCE, base_fee, fee_percentage, GRIEFING_PENALTY_RATE)


def run_simulation(number_of_blocks, network):

    htlc_counter = 0
    while BLOCKCHAIN_INSTANCE.block_number < number_of_blocks:
        sender_node = random.choice(network.nodes)
        # find receiver node
        receiver_node = sender_node
        while receiver_node == sender_node:
            receiver_node = random.choice(network.nodes)

        amount_in_satoshi = how_much_to_send()
        visited_nodes_to_min_hops, path_map = network.find_shortest_path(sender_node, amount_in_satoshi,
                                                                         GRIEFING_PENALTY_RATE)
        if receiver_node in visited_nodes_to_min_hops:
            nodes_between = path_map[receiver_node]
            METRICS_COLLECTOR_INSTANCE.average(PATH_LENGTH_AVG, len(nodes_between))
            send_htlc_successfully = sender_node.start_transaction(receiver_node, amount_in_satoshi, nodes_between)
            if send_htlc_successfully:
                METRICS_COLLECTOR_INSTANCE.count(SEND_SUCCESSFULLY)
            else:
                METRICS_COLLECTOR_INSTANCE.count(SEND_FAILED)
        else:
            METRICS_COLLECTOR_INSTANCE.count(NO_PATH_FOUND)

        htlc_counter += 1
        if htlc_counter == HTLCS_PER_BLOCK:
            htlc_counter = 0
            BLOCKCHAIN_INSTANCE.wait_k_blocks(1)
            total_locked_fund = 0
            for node in network.nodes:
                total_locked_fund += node.locked_funds
            METRICS_COLLECTOR_INSTANCE.average(BLOCK_LOCKED_FUND, total_locked_fund)
            print(f"increase block number. current is {BLOCKCHAIN_INSTANCE.block_number}")
            FUNCTION_COLLECTOR_INSTANCE.run()

    min_block_to_reach = FUNCTION_COLLECTOR_INSTANCE.get_min_k()
    while min_block_to_reach and BLOCKCHAIN_INSTANCE.block_number < min_block_to_reach:
        BLOCKCHAIN_INSTANCE.wait_k_blocks(min_block_to_reach - BLOCKCHAIN_INSTANCE.block_number)
        FUNCTION_COLLECTOR_INSTANCE.run()
        min_block_to_reach = FUNCTION_COLLECTOR_INSTANCE.get_min_k()
    close_channel_and_log_metrics(network)
    metrics = METRICS_COLLECTOR_INSTANCE.get_metrics()
    metrics_str = '\n'.join([f'\t{k}: {v}' for k, v in metrics.items()])
    print(f"Metrics of this run: \n{metrics_str}")
    print(f"Json Metrics: {json.dumps(metrics)}")
    return metrics


def close_channel_and_log_metrics(network):
    for node in network.nodes:
        for other_node in network.edges[node]:
            node.close_channel(other_node)

        if type(node) is lightning_node.LightningNodeSoftGriefing:
            METRICS_COLLECTOR_INSTANCE.average(GRIEFING_SOFT_NODE_BALANCE_AVG,
                                               BLOCKCHAIN_INSTANCE.get_balance_for_node(node))
        elif type(node) is lightning_node.LightningNode:
            METRICS_COLLECTOR_INSTANCE.average(HONEST_NODE_BALANCE_AVG,
                                               BLOCKCHAIN_INSTANCE.get_balance_for_node(node))
        # if type(node) is lightning_node.LightningNodeGriefing:
        #     METRICS_COLLECTOR_INSTANCE.average(GRIEFING_NODE_BALANCE_AVG,
        #                                        BLOCKCHAIN_INSTANCE.get_balance_for_node(node))


def simulation_details(func):
    def wrapper(*args, **kwargs):
        func_args = inspect.signature(func).bind(*args, **kwargs)
        func_args.apply_defaults()
        func_args_str = ", ".join("{} = {!r}".format(*item) for item in func_args.arguments.items())
        print(f"Start to run {func.__qualname__} with arguments: ( {func_args_str} )")
        starting_time = time.time()
        try:
            res = func(*args, **kwargs)
        except Exception as e:
            time_took = time.time() - starting_time
            print(f"Finish the run in {int(time_took)}s.")
            raise e
        return res

    return wrapper


def create_network(number_of_nodes, soft_griefing_percentage):
    network = Network()
    number_of_soft_griefing_nodes = int(soft_griefing_percentage * number_of_nodes)
    for _ in range(number_of_nodes - number_of_soft_griefing_nodes):
        network.add_node(create_node())
    for _ in range(number_of_soft_griefing_nodes):
        network.add_node(create_node(True))
    return network


def generate_network_from_snapshot(json_data, soft_griefing_percentage):
    json_data['edges'] = list(filter(lambda x: x['node1_policy'] and x['node2_policy'], json_data['edges']))
    json_data['edges'] = list(filter(lambda x: not (x['node1_policy']['disabled'] or
                                                    x['node2_policy']['disabled']), json_data['edges']))

    nodes = {}
    number_of_nodes = len(json_data['nodes'])
    number_of_soft_griefing_nodes = int(soft_griefing_percentage * number_of_nodes)
    for node in json_data['nodes'][:number_of_soft_griefing_nodes]:
        nodes[node['pub_key']] = create_node()
    for node in json_data['nodes'][number_of_soft_griefing_nodes:]:
        nodes[node['pub_key']] = create_node(True)
    network = Network(list(nodes.values()))
    for edge in json_data['edges']:
        network.add_edge(nodes[edge['node1_pub']], nodes[edge['node2_pub']], int(int(edge['capacity']) / 2))
    return network


@simulation_details
def simulate_snapshot_network(soft_griefing_percentage=0.05, number_of_blocks=15,
                              snapshot_path='snapshot/LN_2020.05.21-08.00.01.json'):
    with open(snapshot_path, encoding="utf-8") as f:
        json_data = json.load(f)

    network = generate_network_from_snapshot(json_data, soft_griefing_percentage)

    return run_simulation(number_of_blocks, network)


# Redundancy network functions
def generate_redundancy_network(number_of_nodes, soft_griefing_percentage):
    # connect 2 nodes if differ by 10 to the power of n(1...floor(log_10(number_of_nodes))+1)
    #   modulo 10^floor(log_10(number_of_nodes))
    network = create_network(number_of_nodes, soft_griefing_percentage)
    n = int(math.log(number_of_nodes, 10))
    jump_indexes = [10 ** i for i in range(n+1)]
    for i in range(number_of_nodes):
        for index_to_jump in jump_indexes:
            next_index = i + index_to_jump
            if next_index >= number_of_nodes:
                next_index -= number_of_nodes
            if next_index != i:
                channel_starting_balance = random.choices(MSAT_CHANNEL_CAPACITY,
                                                          weights=MSAT_CHANNEL_CAPACITY_PROB, k=1)[0]
                network.add_edge(network.nodes[i], network.nodes[next_index], channel_starting_balance)
    return network


@simulation_details
def simulate_redundancy_network(number_of_nodes=100, soft_griefing_percentage=0.05, number_of_blocks=15):
    network = generate_redundancy_network(number_of_nodes, soft_griefing_percentage)
    return run_simulation(number_of_blocks, network)


# Randomly network functions
def generate_network_randomly(number_of_nodes, soft_griefing_percentage, channel_per_node):
    network = create_network(number_of_nodes, soft_griefing_percentage)
    for node in network.nodes:
        nodes_to_connect = random.sample(network.nodes, channel_per_node)
        nodes_to_connect.remove(node)
        for node_to_connect in nodes_to_connect:
            channel_starting_balance = random.choices(MSAT_CHANNEL_CAPACITY,
                                                      weights=MSAT_CHANNEL_CAPACITY_PROB, k=1)[0]
            network.add_edge(node, node_to_connect, channel_starting_balance)
    return network


@simulation_details
def simulate_random_network(number_of_nodes=100, soft_griefing_percentage=0.05, number_of_blocks=15,
                            channel_per_node=10):
    network = generate_network_randomly(number_of_nodes, soft_griefing_percentage, channel_per_node)
    return run_simulation(number_of_blocks, network)


def run_multiply_simulation():
    number_of_nodes = 100
    number_of_blocks = 15
    soft_griefing_percentages = [0.01, 0.05, 0.1, 0.15]
    simulation_metrics = []

    for soft_griefing_percentage in soft_griefing_percentages:
        parameters = {"number_of_nodes": number_of_nodes,
                      "soft_griefing_percentage": soft_griefing_percentage,
                      "number_of_blocks": number_of_blocks}
        metrics = simulate_redundancy_network(**parameters)
        simulation_metrics.append({'metrics': metrics, 'parameters': parameters})
        BLOCKCHAIN_INSTANCE.init_parameters()
        METRICS_COLLECTOR_INSTANCE.init_parameters()
        FUNCTION_COLLECTOR_INSTANCE.init_parameters()
    print(simulation_metrics)
    timestamp = datetime.timestamp(datetime.now())
    with open(f"simulation_results/{timestamp}.json", 'w') as f:
        for s in simulation_metrics:
            f.write(json.dumps(s) + '\n')


def main():
    fire.Fire({'random': simulate_random_network, 'redundancy': simulate_redundancy_network,
               'snapshot': simulate_snapshot_network, 'run_all': run_multiply_simulation})


if __name__ == '__main__':
    main()

