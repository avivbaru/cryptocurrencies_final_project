import random
import math
from enum import Enum

import fire
import json
import lightning_node
from datetime import datetime
from network import Network
import networkx as nx
from singletons import *

# metrics names

# parameters for runs
CAPACITY_IN_CHANNEL_BETWEEN_VICTIM_ATTACKER2 = 1050000000000
MIN_TO_SEND = 100
MAX_TO_SEND = 1000000000
# MSAT_AMOUNTS_TO_SEND = [1000, 10000, 100000, 1000000, 10000000, 100000000]
MSAT_AMOUNTS_TO_SEND = 10000
# MSAT_CHANNEL_CAPACITY = [500000000, 1000000000, 1500000000, 2000000000, 2500000000, 3000000000, 3500000000, 4500000000,
#                          5000000000, 5500000000, 8500000000, 10500000000]
MSAT_CHANNEL_CAPACITY = 550000
# MSAT_CHANNEL_CAPACITY_PROB = [0.477, 0.110, 0.109, 0.019, 0.051, 0.013, 0.023, 0.015, 0.007, 0.044, 0.015, 0.024]
# MSAT_CHANNEL_CAPACITY_PROB = [1]
# BASE_FEE = [100, 200, 300, 400, 500, 600, 800, 900, 1000]
# BASE_FEE_PROB = [0.019, 0.003, 0.005, 0.019, 0.011, 0.002, 0.011, 0.012, 0.591]
BASE_FEE = 100
# BASE_FEE_PROB = [1]
# FEE_RATE = [100, 200, 500, 1000]
# FEE_RATE_PROB = [0.597, 0.007, 0.006, 0.046]
FEE_RATE = 500
# FEE_RATE_PROB = [1]
STARTING_BALANCE = 17000000000 * 1000  # so the node have enough balance to create all channels
GRIEFING_PENALTY_RATE = 0.001
HTLCS_PER_BLOCK = 1
SIGMA = 0.1
NUMBER_OF_NODES = 1000
# NUMBER_OF_NODES = 200
NUMBER_OF_BLOCKS = 15 * 144
SNAPSHOT_PATH = 'snapshot/LN_2020.05.21-08.00.01.json'
SOFT_GRIEFING_PROBABILITY = 0.5
GRIEFING_PROBABILITY = 0.5
DELTA_DEFAULT = 70
MAX_NUMBER_OF_BLOCKS_TO_RESPONSE_DEFAULT = 6


class NodeType(str, Enum):
    SOFT_GRIEFING = "soft griefing"
    SOFT_GRIEFING_BUSY_NETWORK = "soft griefing - locking funds in network"
    SOFT_GRIEFING_DOS_ATTACK = "dos attack"


class NetworkType(str, Enum):
    REDUNDANCY = "redundancy"
    SNAPSHOT = "snapshot"


NUMBER_OF_ATTACKERS_TO_CREATE = {NetworkType.REDUNDANCY: {NodeType.SOFT_GRIEFING: 2, NodeType.SOFT_GRIEFING_BUSY_NETWORK: 3,
                                                          NodeType.SOFT_GRIEFING_DOS_ATTACK: 1},
                                 NetworkType.SNAPSHOT: {NodeType.SOFT_GRIEFING: 2, NodeType.SOFT_GRIEFING_BUSY_NETWORK: 3,
                                                        NodeType.SOFT_GRIEFING_DOS_ATTACK: 1}}


def how_much_to_send():
    amount = int(min(max(random.gauss(MSAT_AMOUNTS_TO_SEND, SIGMA), MIN_TO_SEND), MAX_TO_SEND))
    METRICS_COLLECTOR_INSTANCE.average(TRANSACTION_AMOUNT_AVG, amount)
    return amount


def create_node(delta, max_number_of_block_to_respond, attacker_node_type=None):
    # divide by million to get the rate per msat
    fee_percentage = FEE_RATE / 1000000
    if NodeType.SOFT_GRIEFING == attacker_node_type:
        return lightning_node.LightningNodeSoftGriefing(STARTING_BALANCE, BASE_FEE, fee_percentage,
                                                        GRIEFING_PENALTY_RATE, delta, max_number_of_block_to_respond,
                                                        block_amount_to_send_transaction=10)
    if NodeType.SOFT_GRIEFING_BUSY_NETWORK == attacker_node_type:
        return lightning_node.LightningNodeSoftGriefing(STARTING_BALANCE, BASE_FEE, fee_percentage,
                                                        GRIEFING_PENALTY_RATE, delta, max_number_of_block_to_respond,
                                                        block_amount_to_send_transaction=3)
    if NodeType.SOFT_GRIEFING_DOS_ATTACK == attacker_node_type:
        return lightning_node.LightningNodeDosAttack(STARTING_BALANCE, BASE_FEE, fee_percentage,
                                                     GRIEFING_PENALTY_RATE, delta, max_number_of_block_to_respond,
                                                     block_amount_to_send_transaction=7)
    return lightning_node.LightningNode(STARTING_BALANCE, BASE_FEE, fee_percentage, GRIEFING_PENALTY_RATE, delta,
                                        max_number_of_block_to_respond)


def run_simulation(network, use_gp_protocol, attackers, victims, simulate_attack):
    counter = 0
    attacker2 = [attacker.get_peer() for attacker in attackers]
    nodes_to_simulate = [node for node in network.nodes if node not in attackers and node not in victims and node not in
                         attacker2]
    while BLOCKCHAIN_INSTANCE.block_number < NUMBER_OF_BLOCKS:
        sender_node = random.choice(nodes_to_simulate)
        # find receiver node
        receiver_node = random.choice(nodes_to_simulate)
        while receiver_node == sender_node:
            receiver_node = random.choice(nodes_to_simulate)

        amount_in_msat = how_much_to_send()
        if simulate_attack:
            for attacker in attackers:
                if attacker.should_send_attack():
                    amount_to_send = attacker.how_much_to_send()
                    if attacker.get_peer():
                        if attacker.get_victim():
                            # soft griefing to specific victim
                            should_try_to_send_transaction = amount_to_send > 0
                            while should_try_to_send_transaction:
                                result = send_attack_transaction(network, attacker.get_victim(), attacker, attacker.get_peer(),
                                                                 use_gp_protocol, amount_to_send)
                                amount_to_send = amount_to_send // 2
                                should_try_to_send_transaction = amount_to_send > 0 and not result
                        else:
                            # soft griefing to make busy network
                            should_try_to_send_transaction = amount_to_send > 0
                            while should_try_to_send_transaction:
                                result = find_path_and_send_transaction(network, attacker.get_peer(), attacker, use_gp_protocol,
                                                                        amount_to_send)
                                amount_to_send = amount_to_send // 2
                                should_try_to_send_transaction = amount_to_send > 0 and not result
                    else:
                        # Dos attack to specific victim
                        find_path_and_send_transaction(network, attacker.get_victim(), attacker, use_gp_protocol,
                                                       attacker.how_much_to_send())
                        should_try_to_send_transaction = amount_to_send > 0
                        while should_try_to_send_transaction:
                            result = find_path_and_send_transaction(network, attacker.get_victim(), attacker, use_gp_protocol,
                                                                    amount_to_send)
                            amount_to_send = amount_to_send // 2
                            should_try_to_send_transaction = amount_to_send > 0 and not result
        if find_path_and_send_transaction(network, receiver_node, sender_node, use_gp_protocol, amount_in_msat):
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
    close_channel_and_log_metrics(network, victims)
    metrics = METRICS_COLLECTOR_INSTANCE.get_metrics()
    add_more_metrics(metrics)
    metrics_str = '\n'.join([f'\t{k}: {v:,}' for k, v in metrics.items()])
    print(f"Metrics of this run: \n{metrics_str}")
    return metrics


def send_attack_transaction(network, victim_node, sender_node, peer_sender_node, use_gp_protocol, amount_in_msat):
    node_to_min_to_send, node_to_path = network.find_shortest_path(victim_node, sender_node, amount_in_msat,
                                                                   GRIEFING_PENALTY_RATE, use_gp_protocol)
    nodes_between = node_to_path.get(sender_node)
    if nodes_between:
        nodes_between = [victim_node] + nodes_between[:-1]
        if Network.is_griefing_possible(nodes_between, sender_node, node_to_min_to_send, GRIEFING_PENALTY_RATE,
                                        node_to_min_to_send[sender_node]):
            node_to_path[sender_node] = [victim_node] + node_to_path[sender_node]
            return send_transaction(peer_sender_node, sender_node, use_gp_protocol, amount_in_msat, node_to_path)
    return False


def find_path_and_send_transaction(network, receiver_node, sender_node, use_gp_protocol, amount_in_msat):
    node_to_min_to_send, node_to_path = network.find_shortest_path(receiver_node, sender_node, amount_in_msat,
                                                                   GRIEFING_PENALTY_RATE, use_gp_protocol)
    return send_transaction(receiver_node, sender_node, use_gp_protocol, amount_in_msat, node_to_path)


def send_transaction(receiver_node, sender_node, use_gp_protocol, amount_in_msat, node_to_path):
    if sender_node in node_to_path:
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


def close_channel_and_log_metrics(network, victims):
    for node in network.nodes:
        for other_node in network.edges[node]:
            node.close_channel(other_node)

        if node in victims:
            METRICS_COLLECTOR_INSTANCE.average(VICTIM_NODE_BALANCE_AVG, BLOCKCHAIN_INSTANCE.get_balance_for_node(node))
        elif type(node) is lightning_node.LightningNode:
            METRICS_COLLECTOR_INSTANCE.average(HONEST_NODE_BALANCE_AVG, BLOCKCHAIN_INSTANCE.get_balance_for_node(node))


def add_more_metrics(metrics):
    metrics[LOCKED_FUND_PER_TRANSACTION] = metrics.get(TOTAL_LOCKED_FUND_IN_EVERY_BLOCKS, 0) / \
                                           metrics.get(TRANSACTIONS_PASSED_THROUGH, 10000000000000000000000000)
    metrics["Victim: " + LOCKED_FUND_PER_TRANSACTION] = metrics.get("Victim: " + TOTAL_LOCKED_FUND_IN_EVERY_BLOCKS, 0) / \
                                                        metrics.get("Victim: " + TRANSACTIONS_PASSED_THROUGH,
                                                                    10000000000000000000000000) # to get zero if no transactions


def create_network(attacker_node_type, delta, max_number_of_block_to_respond):
    network = Network()
    number_of_attackers_to_create = NUMBER_OF_ATTACKERS_TO_CREATE[NetworkType.REDUNDANCY].get(attacker_node_type, 1)
    attackers, victims, attackers2 = create_attacker_and_victim(network, attacker_node_type, delta,
                                                                max_number_of_block_to_respond, number_of_attackers_to_create)
    number_of_special_nodes = len(attackers) + len(victims) + \
                              (len(attackers2) if attacker_node_type != NodeType.SOFT_GRIEFING else 0)
    number_of_nodes_to_create = NUMBER_OF_NODES - number_of_special_nodes
    for _ in range(number_of_nodes_to_create):
        network.add_node(create_node(delta, max_number_of_block_to_respond))
    random.shuffle(network.nodes)
    return network, attackers, victims, attackers2


def create_attacker_and_victim(network, attacker_node_type, delta, max_number_of_block_to_respond, number_of_attackers=1):
    attackers = []
    victims = []
    attackers2 = []
    if attacker_node_type:
        for _ in range(number_of_attackers):
            attacker = create_node(delta, max_number_of_block_to_respond, attacker_node_type)
            network.add_node(attacker)
            attackers.append(attacker)
            if attacker_node_type != NodeType.SOFT_GRIEFING_BUSY_NETWORK:
                victim = create_node(delta, max_number_of_block_to_respond)
                victim.set_as_victim()
                attacker.set_victim(victim)
                attacker.set_fee_percentage(victim.fee_percentage)
                attacker.set_base_fee(victim.base_fee)
                network.add_node(victim)
                victims.append(victim)
            if attacker_node_type != NodeType.SOFT_GRIEFING_DOS_ATTACK:
                attacker2 = create_node(delta, max_number_of_block_to_respond, attacker_node_type)
                attacker.set_peer(attacker2)
                attackers2.append(attacker2)
                if attacker_node_type == NodeType.SOFT_GRIEFING:
                    network.add_edge(attacker2, victim, CAPACITY_IN_CHANNEL_BETWEEN_VICTIM_ATTACKER2, True)
                else:
                    network.add_node(attacker2)
    return attackers, victims, attackers2


def find_largest_connected_component(json_data):
    G = nx.Graph()

    for node in json_data['nodes']:
        G.add_node(node['pub_key'])

    for edge in json_data['edges']:
        G.add_edge(edge['node1_pub'], edge['node2_pub'], capacity=edge['capacity'])
    G.remove_nodes_from(list(nx.isolates(G)))

    largest_connected_component = max(nx.connected_components(G), key=len)
    return G.subgraph(largest_connected_component).copy()


def generate_network_from_snapshot(attacker_node_type, delta, max_number_of_block_to_respond):
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        json_data = json.load(f)
    json_data['edges'] = list(filter(lambda x: x['node1_policy'] and x['node2_policy'], json_data['edges']))
    json_data['edges'] = list(filter(lambda x: not (x['node1_policy']['disabled'] or
                                                    x['node2_policy']['disabled']), json_data['edges']))
    largest_connected_component = find_largest_connected_component(json_data)
    pub_key_to_create = list(largest_connected_component.nodes)
    edges_to_create = largest_connected_component.edges

    nodes = {}
    network = Network()
    number_of_attackers_to_create = NUMBER_OF_ATTACKERS_TO_CREATE[NetworkType.SNAPSHOT].get(attacker_node_type, 1)
    attackers, victims, attackers2 = create_attacker_and_victim(network, attacker_node_type, delta,
                                                                max_number_of_block_to_respond, number_of_attackers_to_create)

    for pub_key in pub_key_to_create:
        nodes[pub_key] = create_node(delta, max_number_of_block_to_respond)

    number_of_special_nodes = len(attackers) + len(victims) + \
                              (len(attackers2) if attacker_node_type != NodeType.SOFT_GRIEFING else 0)
    rand_numbers = random.sample(range(len(pub_key_to_create)), number_of_special_nodes)
    node_index = 0
    for attacker in attackers:
        nodes[pub_key_to_create[rand_numbers[node_index]]] = attacker
        node_index += 1
    for victim in victims:
        nodes[pub_key_to_create[rand_numbers[node_index]]] = victim
        node_index += 1
    if attacker_node_type != NodeType.SOFT_GRIEFING:
        for attacker2 in attackers2:
            nodes[pub_key_to_create[rand_numbers[node_index]]] = attacker2
            node_index += 1

    network.nodes = list(nodes.values())
    for edge in edges_to_create:
        network.add_edge(nodes[edge[0]], nodes[edge[1]], int(int(edges_to_create[edge]['capacity']) / 2))

    for attacker2 in attackers2:
        if attacker2 not in network.nodes:
            network.add_node(attacker2)

    return network, attackers, victims


# Redundancy network functions
def generate_redundancy_network(attacker_node_type, delta, max_number_of_block_to_respond):
    # connect 2 nodes if differ by 10 to the power of n(1...floor(log_10(number_of_nodes))+1)
    #   modulo 10^floor(log_10(number_of_nodes))
    network, attackers, victims, attackers2 = create_network(attacker_node_type, delta, max_number_of_block_to_respond)
    n = int(math.log(NUMBER_OF_NODES, 10))
    jump_indexes = [10 ** i for i in range(n + 1)]
    for i in range(NUMBER_OF_NODES):
        for index_to_jump in jump_indexes:
            next_index = i + index_to_jump
            if next_index >= NUMBER_OF_NODES:
                next_index -= NUMBER_OF_NODES
            if next_index != i:
                network.add_edge(network.nodes[i], network.nodes[next_index], MSAT_CHANNEL_CAPACITY)

    if attackers2:
        for attacker2 in attackers2:
            if attacker2 not in network.nodes:
                network.add_node(attacker2)
    return network, attackers, victims


def build_and_run_simulation(file_to_write, attacker_node_type, delta, max_number_of_block_to_respond, network_topology):
    random.seed()
    seed = random.randint(0, 10000000000000)
    for change_param in [True, False]:
        random.seed(seed)
        if network_topology == NetworkType.REDUNDANCY:
            network, attackers, victims = generate_redundancy_network(attacker_node_type, delta, max_number_of_block_to_respond)
        elif network_topology == NetworkType.SNAPSHOT:
            network, attackers, victims = generate_network_from_snapshot(attacker_node_type, delta,
                                                                         max_number_of_block_to_respond)
        else:
            raise Exception("got invalid network_topology name!")
        use_gp_protocol = attacker_node_type is not None or change_param
        simulate_attack = attacker_node_type is not None and change_param
        parameters = {"attacker_node_type": attacker_node_type,
                      "use_gp_protocol": use_gp_protocol,
                      "simulate_attack": simulate_attack,
                      "delta": delta,
                      "max_number_of_block_to_respond": max_number_of_block_to_respond,
                      'network_topology': network_topology}
        print(f"parameters for the run: {parameters}")
        metrics = run_simulation(network, use_gp_protocol, attackers, victims, simulate_attack)
        add_more_metrics(metrics)
        file_to_write.write(f"{json.dumps({'metrics': metrics, 'parameters': parameters})}\n")
        file_to_write.flush()
        BLOCKCHAIN_INSTANCE.init_parameters()
        METRICS_COLLECTOR_INSTANCE.init_parameters()
        FUNCTION_COLLECTOR_INSTANCE.init_parameters()


def run_multiple_simulation():
    # network_topologies = [NetworkType.REDUNDANCY, NetworkType.SNAPSHOT]
    network_topologies = [NetworkType.REDUNDANCY]
    node_types = [NodeType.SOFT_GRIEFING, NodeType.SOFT_GRIEFING_BUSY_NETWORK, NodeType.SOFT_GRIEFING_DOS_ATTACK]
    delta_node_type = NodeType.SOFT_GRIEFING_DOS_ATTACK
    deltas = [40, 70, 100]
    max_numbers_of_block_to_respond = [2, 6, 10]
    try:
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        with open(f"simulation_results/{current_time}_rawdata", 'w') as f:
            for network_topology in network_topologies:
                for node_type in node_types:
                    build_and_run_simulation(f, node_type, DELTA_DEFAULT, MAX_NUMBER_OF_BLOCKS_TO_RESPONSE_DEFAULT,
                                             network_topology)

                for max_number_of_block_to_respond in max_numbers_of_block_to_respond:
                    build_and_run_simulation(f, None, DELTA_DEFAULT, max_number_of_block_to_respond, network_topology)

                for delta in deltas:
                    # use dos attack to test the affect
                    build_and_run_simulation(f, delta_node_type, delta, MAX_NUMBER_OF_BLOCKS_TO_RESPONSE_DEFAULT,
                                             network_topology)

    finally:
        f.close()


def main():
    fire.Fire({'run_all': run_multiple_simulation})


if __name__ == '__main__':
    main()
