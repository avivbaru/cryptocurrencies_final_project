from typing import Dict, List, Tuple, Callable, Optional, Set
import random
import string
import contract_htlc as cn
import contract_htlc_gp as cn_gp
import channel_manager as cm
from singletons import *

BLOCKS_IN_DAY = 144

BLOCK_IN_DAY = 5

APPEAL_PERIOD = 3  # the appeal period in blocks.
STARTING_SERIAL = 0  # first serial number


def random_delay_node(f):
    def wrapper(self, *args):
        if random.uniform(0, 1) <= self._probability:
            FUNCTION_COLLECTOR_INSTANCE.append(lambda: f(self, *args), BLOCKCHAIN_INSTANCE.block_number + 1)
        else:
            return f(self, *args)
    return wrapper



class TransactionInfo:
    def __init__(self, transaction_id: int, amount_in_wei: int, penalty: int, hash_x: int, hash_r: int,
                 expiration_block_number: int, delta_wait_time: int, previous_node: 'LightningNode' = None,
                 next_node: 'LightningNode' = None, delta: int = None):
        # TODO: delta is a safe measure - do we need it?
        self._id = transaction_id
        self._amount_in_wei = amount_in_wei
        self._penalty = penalty
        self._hash_x = hash_x
        self._hash_r = hash_r
        self._expiration_block_number = expiration_block_number
        self._delta = delta
        self._delta_wait_time = delta_wait_time
        self._previous_node = previous_node
        self._next_node = next_node

    @property
    def hash_x(self):
        return self._hash_x

    @property
    def hash_r(self):
        return self._hash_r

    @property
    def id(self) -> int:
        return self._id

    @property
    def amount_in_wei(self) -> int:
        return self._amount_in_wei

    @property
    def penalty(self):
        return self._penalty

    @property
    def expiration_block_number(self) -> int:
        return self._expiration_block_number

    @property
    def delta_wait_time(self) -> int:
        return self._delta_wait_time

    @property
    def previous_node(self):
        return self._previous_node

    @property
    def next_node(self):
        return self._next_node

    @staticmethod
    def generate_id() -> int:
        id_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return hash(id_str)

class LightningNode:
    def __init__(self, balance: int, fee_percentage: float = 0.1, griefing_penalty_rate: float = 0.01):
        self._address = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self._other_nodes_to_channels: Dict[str, cm.Channel] = {}
        self._hash_image_x_to_preimage: Dict[int, str] = {}
        self._hash_image_r_to_preimage: Dict[int, str] = {}
        self._channels: Dict[str, cm.Channel] = {}
        self._locked_funds: int = 0
        self._balance = balance
        self._fee_percentage = fee_percentage
        self._griefing_penalty_rate = griefing_penalty_rate  # TODO: maybe have this as an attribute of the blockchain
        self._pending_contracts: Set = set()
        self._transaction_id_to_transaction_info: Dict[int, TransactionInfo] = {}
        self._transaction_id_to_forward_contracts: Dict[int, 'cn.ContractForward'] = {}
        self._transaction_id_to_cancellation_contracts: Dict[int, 'cn.ContractCancellation'] = {}
        self._transaction_id_to_htlc_contracts: Dict[int, 'cn.Contract_HTLC'] = {}
        self._probability = 1

        BLOCKCHAIN_INSTANCE.add_node(self, balance)

    @property
    def address(self):
        """
        Returns the address of this node.
        """
        return self._address

    @property
    def locked_funds(self):
        """
        Returns the address of this node.
        """
        return self._locked_funds

    @property
    def fee_percentage(self):
        return self._fee_percentage

    def get_capacity_left(self, other_node):
        if other_node.address in self._other_nodes_to_channels:
            channel = self._other_nodes_to_channels[other_node.address]
            return channel.amount_owner1_can_transfer_to_owner2 if channel.is_owner1(self) else \
                channel.amount_owner2_can_transfer_to_owner1

    def get_fee_for_transfer_amount(self, amount_in_wei: int) -> int:
        return int(self._fee_percentage * amount_in_wei)

    def establish_channel(self, other_node: 'LightningNode', amount_in_wei: int) -> cm.Channel:
        channel_data = cm.ChannelData(self, other_node)
        default_split = cm.MessageState(amount_in_wei, 0)
        channel = other_node.notify_of_channel(channel_data, default_split)
        self._other_nodes_to_channels[other_node.address] = channel
        self._channels[channel_data.address] = channel
        self._balance -= amount_in_wei

        return channel

    def notify_of_channel(self, channel_data: cm.ChannelData, default_split: cm.MessageState) -> cm.Channel:
        assert self._balance >= channel_data.total_wei
        channel = cm.Channel(channel_data, default_split)
        self._other_nodes_to_channels[channel_data.owner1.address] = channel
        self._channels[channel_data.address] = channel
        return channel

    def add_money_to_channel(self, channel: cm.Channel, amount_in_wei: int):
        assert self._balance >= amount_in_wei
        channel.owner2_add_funds(amount_in_wei)
        self._balance -= amount_in_wei
        # TODO: delete unneeded values in dicts

    def start_transaction(self, final_node: 'LightningNode', amount_in_wei, nodes_between: List['LightningNode']):
        hash_x, hash_r = final_node.generate_secret_x_hash(), final_node.generate_secret_r_hash()
        assert nodes_between
        node_to_send = nodes_between[0]

        total_fee = self._calculate_fee_for_route(nodes_between[:-1], amount_in_wei)

        id = TransactionInfo.generate_id()
        delta_waiting_time = ((len(nodes_between) + 1) * BLOCKS_IN_DAY)
        griefing_penalty = self._calculate_griefing_penalty(amount_in_wei + total_fee, delta_waiting_time)
        info = TransactionInfo(id, amount_in_wei + total_fee, griefing_penalty, hash_x, hash_r,
                               BLOCKCHAIN_INSTANCE.block_number +  delta_waiting_time, delta_waiting_time, next_node=node_to_send)
        self._transaction_id_to_transaction_info[id] = info
        self.send_transaction_information(node_to_send, info, nodes_between[1:])
        # 1. propogate transatcion info
        # 2. start cancael contracts
        # 3. start pay contracts

    def _calculate_fee_for_route(self, path_nodes: List['LightningNode'], amount_in_wei: int) -> int:
        transfer_amount = amount_in_wei
        for node in reversed(path_nodes):
            transfer_amount += node.get_fee_for_transfer_amount(transfer_amount)
        return int(transfer_amount) - amount_in_wei

    def _calculate_griefing_penalty(self, amount_in_wei: int, waiting_time):
        return int(self._griefing_penalty_rate * amount_in_wei * waiting_time * 10)

    def send_transaction_information(self, node_to_send: 'LightningNode', transaction_info: TransactionInfo,
                                     nodes_between: List['LightningNode']):
        # TODO: not much logic here... maybe we should give up this function
        node_to_send.receive_transaction_information(self, transaction_info, nodes_between)

    def receive_transaction_information(self, sender: 'LightningNode', previous_transaction_info: TransactionInfo,
                                        nodes_between: List['LightningNode']):
        fee = self.get_fee_for_transfer_amount(previous_transaction_info.amount_in_wei)
        amount_in_wei = previous_transaction_info.amount_in_wei - fee
        waiting_time = previous_transaction_info.expiration_block_number - BLOCKS_IN_DAY
        delta_waiting_time = previous_transaction_info.delta_wait_time - BLOCKS_IN_DAY
        griefing_penalty = previous_transaction_info.penalty + self._calculate_griefing_penalty(amount_in_wei, delta_waiting_time)
        if nodes_between:
            node_to_send = nodes_between[0]
            info = TransactionInfo(previous_transaction_info.id, amount_in_wei, griefing_penalty,
                                   previous_transaction_info.hash_x, previous_transaction_info.hash_r, waiting_time,
                                   delta_waiting_time, sender, node_to_send)
            self._transaction_id_to_transaction_info[previous_transaction_info.id] = info
            self.send_transaction_information(node_to_send, info, nodes_between[1:])
        else:
            info = TransactionInfo(previous_transaction_info.id, amount_in_wei, griefing_penalty,
                                   previous_transaction_info.hash_x, previous_transaction_info.hash_r, waiting_time,
                                   delta_waiting_time, sender)
            self._transaction_id_to_transaction_info[info.id] = info
            self.send_cancellation_contract(info.id)
            r = self._hash_image_r_to_preimage[info.hash_r]
            del self._hash_image_r_to_preimage[info.hash_r]
            FUNCTION_COLLECTOR_INSTANCE.append(lambda: self._handle_cancellation_is_about_to_expire(info.id, r), waiting_time - 1)

    def send_cancellation_contract(self, transaction_id: int):
        assert transaction_id in self._transaction_id_to_transaction_info
        info = self._transaction_id_to_transaction_info[transaction_id]
        channel = self._other_nodes_to_channels[info.previous_node.address]

        cancellation_contract = cn.ContractCancellation(info.penalty, info.hash_x, info.hash_r,
                                                        info.expiration_block_number, channel, self, info.previous_node)
        self._transaction_id_to_cancellation_contracts[transaction_id] = cancellation_contract
        info.previous_node.receive_cancellation_contract(transaction_id, cancellation_contract)

    def receive_cancellation_contract(self, transaction_id: id, contract: 'cn.ContractCancellation'):
        info = self._transaction_id_to_transaction_info[transaction_id]

        if not contract.attached_channel.add_contract(contract):
            return

        if info.previous_node is not None:
            self.send_cancellation_contract(transaction_id)
        else:
            self.send_forward_contract(transaction_id)

    def _handle_cancellation_is_about_to_expire(self, transaction_id: int, r: str):
        if transaction_id not in self._transaction_id_to_cancellation_contracts:
            return

        self.terminate_transaction(transaction_id, r)

    def send_forward_contract(self, transaction_id: int):
        assert transaction_id in self._transaction_id_to_transaction_info

        info = self._transaction_id_to_transaction_info[transaction_id]
        channel = self._other_nodes_to_channels[info.next_node.address]

        forward_contract = cn.ContractForward(info.amount_in_wei, info.hash_x, info.hash_r, info.expiration_block_number,
                                              channel, self, info.next_node)
        self._transaction_id_to_forward_contracts[transaction_id] = forward_contract
        info.next_node.receive_forward_contract(transaction_id, forward_contract)

    def receive_forward_contract(self, transaction_id: int, contract: 'cn.ContractForward'):
        info = self._transaction_id_to_transaction_info[transaction_id]

        if not contract.attached_channel.add_contract(contract):
            return

        if info.next_node is not None:
            self.send_forward_contract(transaction_id)
        else:
            # print("Transaction forward contracts construction successful!")
            x = self._hash_image_x_to_preimage[info.hash_x]
            del self._hash_image_x_to_preimage[info.hash_x]
            self.resolve_transaction(transaction_id, x)

    @random_delay_node
    def resolve_transaction(self, transaction_id: int, x: str):
        info = self._transaction_id_to_transaction_info[transaction_id]
        del self._transaction_id_to_transaction_info[transaction_id]

        if info.next_node is not None and transaction_id in self._transaction_id_to_forward_contracts:
            forward_contract = self._transaction_id_to_forward_contracts[transaction_id]
            del self._transaction_id_to_forward_contracts[transaction_id]
            if forward_contract.is_expired:
                return
            forward_contract.report_x(x)

        if info.previous_node is None:
            # print("Transaction ended!")
            return

        cancellation_contract = self._transaction_id_to_cancellation_contracts[transaction_id]
        del self._transaction_id_to_cancellation_contracts[transaction_id]
        if not cancellation_contract.is_expired:
            return
        cancellation_contract.report_x(x)

        info.previous_node.resolve_transaction(transaction_id, x)

    def terminate_transaction(self, transaction_id: int, r: str):
        if transaction_id not in self._transaction_id_to_forward_contracts:
            return

        info = self._transaction_id_to_transaction_info[transaction_id]
        del self._transaction_id_to_transaction_info[transaction_id]

        if info.next_node is not None:
            forward_contract = self._transaction_id_to_forward_contracts[transaction_id]
            del self._transaction_id_to_forward_contracts[transaction_id]
            if forward_contract.is_expired:
                return
            forward_contract.report_r(r)

        if info.previous_node is None:
            print("Transaction ended (terminated)!")
            return

        cancellation_contract = self._transaction_id_to_cancellation_contracts[transaction_id]
        del self._transaction_id_to_cancellation_contracts[transaction_id]
        if cancellation_contract.is_expired:
            return
        cancellation_contract.report_r(r)

        info.previous_node.terminate_transaction(transaction_id, r)

    def start_regular_htlc_transaction(self, final_node: 'LightningNode', amount_in_wei, nodes_between: List['LightningNode']):
        hash_x = final_node.generate_secret_x_hash()
        assert nodes_between
        node_to_send = nodes_between[0]
        total_fee = self._calculate_fee_for_route(nodes_between[:-1], amount_in_wei)

        id = TransactionInfo.generate_id()
        delta_waiting_time = ((len(nodes_between) + 1) * 144)
        info = TransactionInfo(id, amount_in_wei + total_fee, 0, hash_x, 0, BLOCKCHAIN_INSTANCE.block_number + delta_waiting_time,
                               delta_waiting_time, next_node=node_to_send)
        self._transaction_id_to_transaction_info[id] = info
        self.send_regular_htlc(info, nodes_between[1:])

    def send_regular_htlc(self, transaction_info: TransactionInfo, nodes_between: List['LightningNode']):
        channel = self._other_nodes_to_channels[transaction_info.next_node.address]

        contract = cn.Contract_HTLC(transaction_info.amount_in_wei, transaction_info.hash_x, 0,
                                    transaction_info.expiration_block_number, channel, self, transaction_info.next_node)
        transaction_info.next_node.receive_regular_htlc(self, transaction_info, contract, nodes_between)

    def receive_regular_htlc(self, sender: 'LightningNode', previous_transaction_info: TransactionInfo,
                             contract: 'cn.Contract_HTLC', nodes_between: List['LightningNode']):
        node_to_send = nodes_between[0] if nodes_between else None
        fee = self.get_fee_for_transfer_amount(previous_transaction_info.amount_in_wei)
        amount_in_wei = previous_transaction_info.amount_in_wei - fee
        delta_waiting_time = previous_transaction_info.delta_wait_time - BLOCKS_IN_DAY
        new_info = TransactionInfo(previous_transaction_info.id, amount_in_wei, 0, previous_transaction_info.hash_x, 0,
                                   previous_transaction_info.expiration_block_number - BLOCKS_IN_DAY, delta_waiting_time,
                                   sender, node_to_send)

        self._transaction_id_to_transaction_info[new_info.id] = new_info
        self._transaction_id_to_htlc_contracts[new_info.id] = contract
        contract.attached_channel.add_contract(contract)

        if nodes_between:
            self.send_regular_htlc(new_info, nodes_between[1:])
        else:
            # print("Transaction regular htlc contracts construction successful!")
            x = self._hash_image_x_to_preimage[new_info.hash_x]
            self.resolve_htlc_transaction(new_info.id, x)

    @random_delay_node
    def resolve_htlc_transaction(self, transaction_id: int, x: str):
        info = self._transaction_id_to_transaction_info[transaction_id]
        del self._transaction_id_to_transaction_info[transaction_id]

        if info.previous_node is not None:
            contract = self._transaction_id_to_htlc_contracts[transaction_id]
            if contract.is_expired:
                return
            contract.report_x(x)
        else:
            # print("Transaction (regular htlc) ended!")
            return

        info.previous_node.resolve_htlc_transaction(transaction_id, x)

    def generate_secret_x_hash(self) -> (int, int):
        x = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        hash_image = hash(x)
        self._hash_image_x_to_preimage[hash_image] = x
        return hash_image

    def generate_secret_r_hash(self) -> int:
        r = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        hash_image = hash(r)
        self._hash_image_r_to_preimage[hash_image] = r
        return hash_image

    def close_channel(self, node):
        if node.address not in self._other_nodes_to_channels:
            return

        channel = self._other_nodes_to_channels[node.address]
        del self._other_nodes_to_channels[node.address]
        if channel not in self._channels:
            return
        channel.close_channel()
        self._balance += channel.owner1_balance if channel.is_owner1(self) else channel.owner2_balance
        del self._channels[channel.channel_state.channel_data.address]

    def notify_of_change_in_locked_funds(self, locked_fund):
        self._locked_funds += locked_fund

    def notify_of_closed_channel(self, channel: 'cm.Channel', other_node: 'LightningNode'):
        if channel.channel_state.channel_data.address not in self._channels:
            return
        del self._channels[channel.channel_state.channel_data.address]

        if other_node.address in self._other_nodes_to_channels:
            del self._other_nodes_to_channels[other_node.address]



# class LightningNodeGriefing(LightningNode):
#     def __init__(self, balance: int, fee_percentage: float = 0.1, griefing_penalty_rate: float = 0.01):
#         super().__init__(balance, fee_percentage, griefing_penalty_rate)
#
#     def _start_resolving_contract_off_chain(self, sender: 'LightningNode', contract: cn.Contract_HTLC):
#         return # this waits for expiration, classic griefing. below is "soft griefing"
        # target_block_number = contract.expiration_block_number - 1
        # FUNCTION_COLLECTOR_INSTANCE.append(
        #     self._collector_function_creator(target_block_number,
        #                                      lambda: super(LightningNodeGriefing, self)
        #                                      ._start_resolving_contract_off_chain(sender, contract)))

    # def _collector_function_creator(self, block_number: int, func: Callable[[], None]) -> Callable[[], bool]:
    #     def check_block_and_use_function():
    #         if BLOCKCHAIN_INSTANCE.block_number <= block_number:
    #             return False
    #
    #         print("Griefined!")
    #         func()
    #         return True
    #     return check_block_and_use_function

    # def _notify_other_node_of_resolving_contract(self, other_node: 'LightningNode', contract: cn.Contract_HTLC):
    #     return
        # target_block_number = contract.expiration_block_number - 1
        # FUNCTION_COLLECTOR_INSTANCE.append(
        #     self._collector_function_creator(target_block_number,
        #                                      lambda: super(LightningNodeGriefing, self)
        #                                      ._notify_other_node_of_resolving_contract(other_node, contract)))


# class LightningNodeSoftGriefing(LightningNode):
#     def __init__(self, balance: int, fee_percentage: float = 0.1, griefing_penalty_rate: float = 0.01):
#         super().__init__(balance, fee_percentage, griefing_penalty_rate)
#
#     def _start_resolving_contract_off_chain(self, sender: 'LightningNode', contract: cn.Contract_HTLC):
#         target_block_number = contract.expiration_block_number - 1
#         FUNCTION_COLLECTOR_INSTANCE.append(
#             lambda: super(LightningNodeSoftGriefing, self).
#                 _start_resolving_contract_off_chain(sender, contract), target_block_number)
#
#     def _collector_function_creator(self, func: Callable[[], None]) -> Callable[[], None]:
#         def check_block_and_use_function():
#             func()
#         return check_block_and_use_function
#
#     def _notify_other_node_of_resolving_contract(self, other_node: 'LightningNode', contract: cn.Contract_HTLC):
#         target_block_number = contract.expiration_block_number - 1
#         FUNCTION_COLLECTOR_INSTANCE.append(lambda: super(LightningNodeSoftGriefing, self)
#                                            ._notify_other_node_of_resolving_contract(other_node, contract),
#                                            target_block_number)


# class LightningNodeReverseGriefing(LightningNode):
#     def __init__(self, balance: int, fee_percentage: float = 0.1, griefing_penalty_rate: float = 0.01):
#         super().__init__(balance, fee_percentage, griefing_penalty_rate)
#         self._peers: List['LightningNodeReverseGriefing'] = []
#         self._hash_to_peer: Dict[int, 'LightningNodeReverseGriefing'] = {}
#         self._hash_to_grief: List[int] = []
#         self._hash_to_not_accept_disable: List[int] = []
#
#     @property
#     def peers(self):
#         return self._peers
#
#     def _notify_of_peer(self, peer: 'LightningNodeReverseGriefing'):
#         self._add_peers_from_new_peer(peer)
#         peer._add_peers_from_new_peer(self)
#
#     def _add_peers_from_new_peer(self, peer: 'LightningNodeReverseGriefing'):
#         self._peers.append(peer)
#         self._peers.extend(peer.peers)
#         self._peers.remove(self)
#
#     def _notify_peer_of_hash(self, hash: int):
#         for peer in self._peers:
#             peer._receive_contract_from_peer(hash, peer)
#
#     def _notify_peer_of_hash_not_accept_disable(self, hash: int):
#         self._hash_to_not_accept_disable.append(hash)
#
#     def _receive_contract_from_peer(self, hash: int, peer: 'LightningNodeReverseGriefing'):
#         self._hash_to_peer[hash] = peer
#
#     def receive_htlc(self, sender: 'LightningNode', contract: cn.Contract_HTLC, amount_in_wei: int,
#                      nodes_between: List['LightningNode'], cumulative_griefing_penalty: int = 0):
#         if contract.hash_image in self._hash_to_peer:
#             # Griefing!!!!!!
#             # what happend if there is more then 2?????
#             self._hash_to_peer[contract.hash_image]._notify_peer_of_hash_not_accept_disable(contract.hash_image)
#             return
#         self._notify_peer_of_hash(contract.hash_image)
#         super().receive_htlc(sender, contract, amount_in_wei, nodes_between, cumulative_griefing_penalty)
#
#     # TODO: complete!
#     def decline_contract(self, contract: cn.Contract_HTLC):
#         if contract.hash_image in self._hash_to_not_accept_disable:
#             # getting money!!!!!
#             return
#         super().decline_contract(contract)

    # def _start_resolving_contract_off_chain(self, sender: 'LightningNode', contract: cn.Contract_HTLC):
    #     target_block_number = contract.expiration_block_number - 1
    #     FUNCTION_COLLECTOR_INSTANCE.append(
    #         lambda: super(LightningNodeSoftGriefing, self).
    #             _start_resolving_contract_off_chain(sender, contract), target_block_number)
    #
    # def _collector_function_creator(self, func: Callable[[], None]) -> Callable[[], None]:
    #     def check_block_and_use_function():
    #         func()
    #     return check_block_and_use_function
    #
    # def _notify_other_node_of_resolving_contract(self, other_node: 'LightningNode', contract: cn.Contract_HTLC):
    #     target_block_number = contract.expiration_block_number - 1
    #     FUNCTION_COLLECTOR_INSTANCE.append(lambda: super(LightningNodeSoftGriefing, self)
    #                                        ._notify_other_node_of_resolving_contract(other_node, contract),
    #                                        target_block_number)

