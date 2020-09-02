import random
import time
import math
from enum import Enum

import fire
import json
import inspect
import lightning_node
from datetime import datetime
from network import Network
from singletons import *

# metrics names

# parameters ofr runs
MIN_TO_SEND = 100
MAX_TO_SEND = 1000000000
MSAT_AMOUNTS_TO_SEND = [1000, 10000, 100000, 1000000, 10000000, 100000000]
# MSAT_AMOUNTS_TO_SEND = [1000000]
MSAT_CHANNEL_CAPACITY = [500000000, 1000000000, 1500000000, 2000000000, 2500000000, 3000000000, 3500000000, 4500000000,
                         5000000000, 5500000000, 8500000000, 10500000000]
# MSAT_CHANNEL_CAPACITY = [10000000000]
MSAT_CHANNEL_CAPACITY_PROB = [0.477, 0.110, 0.109, 0.019, 0.051, 0.013, 0.023, 0.015, 0.007, 0.044, 0.015, 0.024]
# MSAT_CHANNEL_CAPACITY_PROB = [1]
BASE_FEE = [0, 100, 200, 300, 400, 500, 600, 800, 900, 1000]
BASE_FEE_PROB = [0.300, 0.019, 0.003, 0.005, 0.019, 0.011, 0.002, 0.011, 0.012, 0.591]
# BASE_FEE = [100]
# BASE_FEE_PROB = [1]
FEE_RATE = [0, 1, 2, 5, 10]
FEE_RATE_PROB = [0.066, 0.597, 0.007, 0.006, 0.046]
# FEE_RATE = [3]
# FEE_RATE_PROB = [1]
STARTING_BALANCE = 17000000000 * 1000  # so the node have enough balance to create all channels
GRIEFING_PENALTY_RATE = 0.001
HTLCS_PER_BLOCK = 1
SIGMA = 0.1
NUMBER_OF_NODES = 200
NUMBER_OF_BLOCKS = 5 * 144
SNAPSHOT_PATH = 'snapshot/LN_2020.05.21-08.00.01.json'
SOFT_GRIEFING_PROBABILITY = 0.5
GRIEFING_PROBABILITY = 0.5
SOFT_GRIEFING_PERCENTAGE_DEFAULT = 0
GRIEFING_PERCENTAGE_DEFAULT = 0
DELTA_DEFAULT = 60
MAX_NUMBER_OF_BLOCKS_TO_RESPONSE_DEFAULT = 4


class NodeType(Enum):
    SOFT_GRIEFING = 1
    GRIEFING = 2
    SOFT_GRIEFING_DOS_ATTACK = 3


def how_much_to_send():
    mu = random.choice(MSAT_AMOUNTS_TO_SEND) # TODO: remove the divide
    amount = int(min(max(random.gauss(mu, SIGMA), MIN_TO_SEND), MAX_TO_SEND))
    METRICS_COLLECTOR_INSTANCE.average(TRANSACTION_AMOUNT_AVG, amount)
    return amount


def create_node(delta, max_number_of_block_to_respond, griefing_type: NodeType = None):
    # divide by million to get the rate per msat
    fee_percentage = random.choices(FEE_RATE, weights=FEE_RATE_PROB, k=1)[0] / 1000000
    base_fee = random.choices(BASE_FEE, weights=BASE_FEE_PROB, k=1)[0]
    METRICS_COLLECTOR_INSTANCE.average(BASE_FEE_LOG, base_fee)
    METRICS_COLLECTOR_INSTANCE.average(FEE_PERCENTAGE, fee_percentage)
    if griefing_type:
        if NodeType.SOFT_GRIEFING == griefing_type:
            return lightning_node.LightningNodeSoftGriefing(STARTING_BALANCE, base_fee, fee_percentage,
                                                            GRIEFING_PENALTY_RATE, delta, max_number_of_block_to_respond,
                                                            probability_to_soft_griefing=SOFT_GRIEFING_PROBABILITY)
        if NodeType.GRIEFING == griefing_type:
            return lightning_node.LightningNodeGriefing(STARTING_BALANCE, base_fee, fee_percentage,
                                                        GRIEFING_PENALTY_RATE, delta, max_number_of_block_to_respond,
                                                        probability_to_griefing=GRIEFING_PROBABILITY)
        if NodeType.SOFT_GRIEFING_DOS_ATTACK == griefing_type:
            return lightning_node.LightningNodeSoftGriefingDosAttack(STARTING_BALANCE, base_fee, fee_percentage,
                                                                     GRIEFING_PENALTY_RATE, delta, max_number_of_block_to_respond)
    return lightning_node.LightningNode(STARTING_BALANCE, base_fee, fee_percentage, GRIEFING_PENALTY_RATE, delta,
                                        max_number_of_block_to_respond)


def run_simulation(network, use_gp_protocol, dos_attack=False):
    attacker_node, victim_node = None, None
    if dos_attack:
        attacker_node = random.choice([node for node in network.nodes
                                       if type(node) is lightning_node.LightningNodeSoftGriefingDosAttack])
        victim_node = random.choice(network.nodes)
        while victim_node == attacker_node:
            victim_node = random.choice(network.nodes)
        attacker_node.set_victim(victim_node)
    counter = 0
    while BLOCKCHAIN_INSTANCE.block_number < NUMBER_OF_BLOCKS:
        sender_node = random.choice(network.nodes)
        # find receiver node
        receiver_node = random.choice(network.nodes)
        while receiver_node == sender_node:
            receiver_node = random.choice(network.nodes)

        if dos_attack:
            send_transaction(network, victim_node, attacker_node, use_gp_protocol)
        if send_transaction(network, receiver_node, sender_node, use_gp_protocol):
            METRICS_COLLECTOR_INSTANCE.count(SEND_TRANSACTION)
        else:
            METRICS_COLLECTOR_INSTANCE.count(NO_PATH_FOUND)

        counter += 1
        if counter == HTLCS_PER_BLOCK:
            counter = 0
            increase_block(1)
            if BLOCKCHAIN_INSTANCE.block_number % 144 == 0:
                print(f"Increase block number. current is {BLOCKCHAIN_INSTANCE.block_number}")

    increase_block(FUNCTION_COLLECTOR_INSTANCE.get_max_k())
    print(f"Final block number is {BLOCKCHAIN_INSTANCE.block_number}")
    close_channel_and_log_metrics(network, dos_attack, attacker_node, victim_node)
    metrics = METRICS_COLLECTOR_INSTANCE.get_metrics()
    metrics_str = '\n'.join([f'\t{k}: {v:,}' for k, v in metrics.items()])
    print(f"Metrics of this run: \n{metrics_str}")
    return metrics


def send_transaction(network, receiver_node, sender_node, use_gp_protocol):
    amount_in_msat = how_much_to_send()
    node_to_min_to_send, node_to_path = network.find_shortest_path(receiver_node, sender_node, amount_in_msat,
                                                                   GRIEFING_PENALTY_RATE, use_gp_protocol)
    if sender_node in node_to_min_to_send:
        nodes_between = list(reversed(node_to_path[sender_node]))[1:]
        nodes_between.append(receiver_node)
        METRICS_COLLECTOR_INSTANCE.average(PATH_LENGTH_AVG, len(nodes_between))
        if use_gp_protocol:
            sender_node.start_transaction(receiver_node, amount_in_msat, nodes_between)
        else:
            sender_node.start_regular_htlc_transaction(receiver_node, amount_in_msat, nodes_between)
        return True
    return False


def increase_block(block_number_to_increase):
    block_number_to_reach = BLOCKCHAIN_INSTANCE.block_number + (block_number_to_increase or 0)
    while BLOCKCHAIN_INSTANCE.block_number < block_number_to_reach:
        min_block_to_reach = FUNCTION_COLLECTOR_INSTANCE.get_min_k() if FUNCTION_COLLECTOR_INSTANCE.get_min_k() is not None \
                                                                    else block_number_to_reach
        min_block_to_reach = min(min_block_to_reach, block_number_to_reach)
        BLOCKCHAIN_INSTANCE.wait_k_blocks(min_block_to_reach - BLOCKCHAIN_INSTANCE.block_number)
        FUNCTION_COLLECTOR_INSTANCE.run()


def close_channel_and_log_metrics(network, dos_attack, attacker_node, victim_node):
    for node in network.nodes:
        for other_node in network.edges[node]:
            node.close_channel(other_node)

        if dos_attack and node == victim_node:
            METRICS_COLLECTOR_INSTANCE.average("Victim node balance", BLOCKCHAIN_INSTANCE.get_balance_for_node(node))
        elif dos_attack and node == attacker_node:
            METRICS_COLLECTOR_INSTANCE.average("Attacker node balance", BLOCKCHAIN_INSTANCE.get_balance_for_node(node))
        elif type(node) is lightning_node.LightningNodeSoftGriefing or type(node) is \
                lightning_node.LightningNodeSoftGriefingDosAttack:
            METRICS_COLLECTOR_INSTANCE.average(GRIEFING_SOFT_NODE_BALANCE_AVG, BLOCKCHAIN_INSTANCE.get_balance_for_node(node))
        elif type(node) is lightning_node.LightningNode:
            METRICS_COLLECTOR_INSTANCE.average(HONEST_NODE_BALANCE_AVG, BLOCKCHAIN_INSTANCE.get_balance_for_node(node))
        elif type(node) is lightning_node.LightningNodeGriefing:
            METRICS_COLLECTOR_INSTANCE.average(GRIEFING_NODE_BALANCE_AVG, BLOCKCHAIN_INSTANCE.get_balance_for_node(node))


def add_more_metrics(metrics):
    metrics[LOCKED_FUND_PER_TRANSACTION_NORMALIZE_BY_AMOUNT_SENT_AVG] = metrics.get(LOCKED_FUND_PER_TRANSACTION_AVG, 0) / \
                                                                        metrics.get(TRANSACTION_AMOUNT_AVG, 1)


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
            raise e
        finally:
            time_took = time.time() - starting_time
            print(f"Finish the run in {int(time_took)}s.")
        return res

    return wrapper


def create_network(soft_griefing_percentage, griefing_percentage, delta, max_number_of_block_to_respond, dos_attack):
    network = Network()
    number_of_nodes = NUMBER_OF_NODES - 1 if dos_attack else NUMBER_OF_NODES
    number_of_soft_griefing_nodes = int(soft_griefing_percentage * number_of_nodes)
    number_of_griefing_nodes = int(griefing_percentage * number_of_nodes)
    if dos_attack:
        network.add_node(create_node(delta, max_number_of_block_to_respond, NodeType.SOFT_GRIEFING_DOS_ATTACK))
    for _ in range(number_of_nodes - number_of_soft_griefing_nodes - number_of_griefing_nodes):
        network.add_node(create_node(delta, max_number_of_block_to_respond))
    for _ in range(number_of_soft_griefing_nodes):
        network.add_node(create_node(delta, max_number_of_block_to_respond, NodeType.SOFT_GRIEFING))
    for _ in range(number_of_griefing_nodes):
        network.add_node(create_node(delta, max_number_of_block_to_respond, NodeType.GRIEFING))
    random.shuffle(network.nodes)
    return network


def generate_network_from_snapshot(json_data, soft_griefing_percentage, griefing_percentage, delta,
                                   max_number_of_block_to_respond):
    json_data['edges'] = list(filter(lambda x: x['node1_policy'] and x['node2_policy'], json_data['edges']))
    json_data['edges'] = list(filter(lambda x: not (x['node1_policy']['disabled'] or
                                                    x['node2_policy']['disabled']), json_data['edges']))

    nodes = {}
    nodes_potential_to_be_attak = ['0227230b7b685f1742b944bfc5d79ddc8c5a90b68499775ee10895f87307d8d22e',
                                   '02ad6fb8d693dc1e4569bcedefadf5f72a931ae027dc0f0c544b34c1c6f3b9a02b',
                                   '03bf7441842433a304a1027abfb75f399cfcf62f75339f15b6c27c24d69100ee50',
                                   '0242a4ae0c5bef18048fbecf995094b74bfb0f7391418d71ed394784373f41e4f3',
                                   '03864ef025fde8fb587d989186ce6a4a186895ee44a926bfc370e2c366597a3f8f',
                                   '0279c22ed7a068d10dc1a38ae66d2d6461e269226c60258c021b1ddcdfe4b00bc4',
                                   '0217890e3aad8d35bc054f43acc00084b25229ecff0ab68debd82883ad65ee8266',
                                   '03abf6f44c355dec0d5aa155bdbdd6e0c8fefe318eff402de65c6eb2e1be55dc3e',
                                   '03bb88ccc444534da7b5b64b4f7b15e1eccb18e102db0e400d4b9cfe93763aa26d',
                                   '0292052c3ab594f7b5e997099f66e8ed51b4342126dcb5c3caa76b38adb725dcdb']
    nodes_potential_to_soft_grief = [edge['node1_pub'] if edge['node2_pub'] in nodes_potential_to_be_attak else edge[
        'node2_pub'] for edge in json_data['edges'] if edge['node1_pub'] in nodes_potential_to_be_attak or edge['node2_pub'] in
                                     nodes_potential_to_be_attak]
    nodes_potential_to_soft_grief = set([pub for pub in nodes_potential_to_soft_grief if pub not in nodes_potential_to_be_attak])
    number_of_nodes = len(json_data['nodes'])
    # number_of_soft_griefing_nodes = int(soft_griefing_percentage * number_of_nodes)
    # number_of_griefing_nodes = int(griefing_percentage * number_of_nodes)

    for node in json_data['nodes']:
        if node['pub_key'] in nodes_potential_to_be_attak:
            nodes[node['pub_key']] = create_node(delta, max_number_of_block_to_respond)
    nodes_potential_to_be_attak_addresses = [nodes[node] for node in nodes]
    for node in json_data['nodes']:
        if node['pub_key'] in nodes_potential_to_soft_grief and random.uniform(0, 1) < soft_griefing_percentage:
            nodes[node['pub_key']] = create_node(delta, max_number_of_block_to_respond, NodeType.SOFT_GRIEFING_DOS_ATTACK,
                                                 nodes_potential_to_be_attak_addresses, 1)
        elif node['pub_key'] in nodes_potential_to_soft_grief and random.uniform(0, 1) < griefing_percentage:
            nodes[node['pub_key']] = create_node(delta, max_number_of_block_to_respond, NodeType.GRIEFING)
        elif nodes.get(node['pub_key']) is None:
            nodes[node['pub_key']] = create_node(delta, max_number_of_block_to_respond)

    # for node in json_data['nodes'][:number_of_soft_griefing_nodes]:
    #     nodes[node['pub_key']] = create_node(delta, max_number_of_block_to_respond, NodeType.SOFT_GRIEFING)
    # for node in json_data['nodes'][number_of_soft_griefing_nodes:number_of_griefing_nodes + number_of_soft_griefing_nodes]:
    #     nodes[node['pub_key']] = create_node(delta, max_number_of_block_to_respond, NodeType.GRIEFING)
    # for node in json_data['nodes'][number_of_griefing_nodes + number_of_soft_griefing_nodes:]:
    #     nodes[node['pub_key']] = create_node(delta, max_number_of_block_to_respond)
    network = Network(list(nodes.values()))
    for edge in json_data['edges']:
        network.add_edge(nodes[edge['node1_pub']], nodes[edge['node2_pub']], int(int(edge['capacity']) / 2))
    return network


@simulation_details
def simulate_snapshot_network(soft_griefing_percentage=0.05, griefing_percentage=0.05, delta=40,
                              max_number_of_block_to_respond=2, use_gp_protocol=True):
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        json_data = json.load(f)

    network = generate_network_from_snapshot(json_data, soft_griefing_percentage, griefing_percentage, delta,
                                             max_number_of_block_to_respond)

    return run_simulation(network, use_gp_protocol)


# Redundancy network functions
def generate_redundancy_network(soft_griefing_percentage, griefing_percentage, delta, max_number_of_block_to_respond, dos_attack):
    # connect 2 nodes if differ by 10 to the power of n(1...floor(log_10(number_of_nodes))+1)
    #   modulo 10^floor(log_10(number_of_nodes))
    network = create_network(soft_griefing_percentage, griefing_percentage, delta, max_number_of_block_to_respond, dos_attack)
    n = int(math.log(NUMBER_OF_NODES, 10))
    jump_indexes = [10 ** i for i in range(n+1)]
    for i in range(NUMBER_OF_NODES):
        for index_to_jump in jump_indexes:
            next_index = i + index_to_jump
            if next_index >= NUMBER_OF_NODES:
                next_index -= NUMBER_OF_NODES
            if next_index != i:
                channel_starting_balance = random.choices(MSAT_CHANNEL_CAPACITY,
                                                          weights=MSAT_CHANNEL_CAPACITY_PROB, k=1)[0]
                METRICS_COLLECTOR_INSTANCE.average(CHANNEL_STARTING_BALANCE, channel_starting_balance)
                network.add_edge(network.nodes[i], network.nodes[next_index], channel_starting_balance)
    return network


@simulation_details
def simulate_redundancy_network(soft_griefing_percentage=0.20, griefing_percentage=0.05, use_gp_protocol=True, delta=40,
                                max_number_of_block_to_respond=5, dos_attack=False):
    network = generate_redundancy_network(soft_griefing_percentage, griefing_percentage, delta,
                                          max_number_of_block_to_respond, dos_attack)
    return run_simulation(network, use_gp_protocol, dos_attack)


def build_and_run_simulation(file_to_write, soft_griefing_percentage, griefing_percentage, use_gp_protocol, delta,
                             max_number_of_block_to_respond, network_topology, dos_attack):
    parameters = {"soft_griefing_percentage": soft_griefing_percentage,
                  "griefing_percentage": griefing_percentage,
                  "use_gp_protocol": use_gp_protocol,
                  "delta": delta,
                  "max_number_of_block_to_respond": max_number_of_block_to_respond,
                  "dos_attack": dos_attack}
    if network_topology == 'redundancy':
        metrics = simulate_redundancy_network(**parameters)
    elif network_topology == 'snapshot':
        metrics = simulate_snapshot_network(**parameters)
    else:
        raise Exception("got invalid network_topology name!")
    parameters.update({'network_topology': network_topology})
    add_more_metrics(metrics)
    file_to_write.write(f"{json.dumps({'metrics': metrics, 'parameters': parameters})}\n")
    file_to_write.flush()
    BLOCKCHAIN_INSTANCE.init_parameters()
    METRICS_COLLECTOR_INSTANCE.init_parameters()
    FUNCTION_COLLECTOR_INSTANCE.init_parameters()


def run_multiple_simulation(is_soft_griefing=True, dos_attack=False):
    soft_griefing_percentages = [0, 0.1, 0.2]
    griefing_percentages = [0]
    if not is_soft_griefing:
        soft_griefing_percentages = [0]
        griefing_percentages = [0.01, 0.1, 0.2]
    use_gp_protocol_options = [True, False]
    network_topologies = ['redundancy']
    deltas = [40, 70, 100]
    max_numbers_of_block_to_respond = [2, 6, 10]
    try:
        timestamp = datetime.timestamp(datetime.now())
        with open(f"simulation_results/{timestamp}_rawdata{'_dos' if dos_attack else ''}", 'w') as f:
            for network_topology in network_topologies:
                for use_gp_protocol in use_gp_protocol_options:
                    for max_number_of_block_to_respond in max_numbers_of_block_to_respond:
                        build_and_run_simulation(f, SOFT_GRIEFING_PERCENTAGE_DEFAULT, GRIEFING_PERCENTAGE_DEFAULT,
                                                 use_gp_protocol, DELTA_DEFAULT, max_number_of_block_to_respond,
                                                 network_topology,dos_attack)
                    for delta in deltas:
                        build_and_run_simulation(f, SOFT_GRIEFING_PERCENTAGE_DEFAULT, GRIEFING_PERCENTAGE_DEFAULT,
                                                 use_gp_protocol, delta, MAX_NUMBER_OF_BLOCKS_TO_RESPONSE_DEFAULT,
                                                 network_topology, dos_attack)

                    for griefing_percentage in griefing_percentages:
                        build_and_run_simulation(f, SOFT_GRIEFING_PERCENTAGE_DEFAULT, griefing_percentage,
                                                 use_gp_protocol, DELTA_DEFAULT, MAX_NUMBER_OF_BLOCKS_TO_RESPONSE_DEFAULT,
                                                 network_topology, dos_attack)

                    for soft_griefing_percentage in soft_griefing_percentages:
                        build_and_run_simulation(f, soft_griefing_percentage, GRIEFING_PERCENTAGE_DEFAULT,
                                                 use_gp_protocol, DELTA_DEFAULT, MAX_NUMBER_OF_BLOCKS_TO_RESPONSE_DEFAULT,
                                                 network_topology, dos_attack)

    finally:
        f.close()


def main():
    fire.Fire({'redundancy': simulate_redundancy_network,
               'snapshot': simulate_snapshot_network, 'run_all': run_multiple_simulation})


if __name__ == '__main__':
    main()

