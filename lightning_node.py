from typing import Dict, List, Optional
import random
import string
import contract_htlc as cn
import channel_manager as cm
from singletons import *

BLOCKS_IN_DAY = 144

APPEAL_PERIOD = 3  # the appeal period in blocks.
STARTING_SERIAL = 0  # first serial number


def random_delay_node(f):
    """
    Wrapper for delaying a given function's execution in order to simulate an internet connection delays.
    @param f: The function to delay.
    """
    def wrapper(self, *args):
        number_of_block_to_wait = random.randint(1, self._max_number_of_block_to_respond)
        FUNCTION_COLLECTOR_INSTANCE.append(lambda: f(self, *args), BLOCKCHAIN_INSTANCE.block_number + number_of_block_to_wait)

    return wrapper


class TransactionInfo:
    """
    Holds all the information regrading a specific transaction.
    """

    def __init__(self, transaction_id: int, amount_in_msat: int, penalty: int, hash_x: int, hash_r: int,
                 expiration_block_number: int, delta_wait_time: int, starting_block: int, path_length: int,
                 previous_node: 'LightningNode' = None, next_node: 'LightningNode' = None):
        """
        @param transaction_id: The id of the transaction.
        @param amount_in_msat: amount to transfer in transaction.
        @param penalty: amount to pay upon griefing.
        @param hash_x: the hash of the transaction's secret for accepting it.
        @param hash_r: the hash of the transaction's secret for terminating it.
        @param expiration_block_number: Block number this transaction will be expired.
        @param delta_wait_time: waiting time to expire.
        @param starting_block: the block number the transaction was sent.
        @param path_length: the length of the path of this transaction.
        @param previous_node: the previous node in the transaction chain.
        @param next_node: the next node in the transaction chain.
        """
        assert amount_in_msat >= 0
        assert penalty >= 0

        self._id = transaction_id
        self._amount_in_mast = amount_in_msat
        self._penalty = penalty
        self._hash_x = hash_x
        self._hash_r = hash_r
        self._expiration_block_number = expiration_block_number
        self._delta_wait_time = delta_wait_time
        self._previous_node = previous_node
        self._next_node = next_node
        self._starting_block = starting_block
        self._path_length = path_length

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
    def amount_in_msat(self) -> int:
        return self._amount_in_mast

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
    def previous_node(self) -> 'LightningNode':
        return self._previous_node

    @property
    def next_node(self) -> 'LightningNode':
        return self._next_node

    @property
    def starting_block(self) -> int:
        return self._starting_block

    @property
    def path_length(self) -> int:
        return self._path_length

    @staticmethod
    def generate_id() -> int:
        id_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return hash(id_str)


class LightningNode:
    """
    Represents an honest node in the network.
    """

    def __init__(self, balance: int, base_fee: int, fee_percentage: float = 0.01, griefing_penalty_rate: float = 0.01,
                 delta: int = 40, max_number_of_block_to_respond: int = 4):
        self._address = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self._other_nodes_to_channels: Dict[str, cm.Channel] = {}
        self._hash_image_x_to_preimage: Dict[int, str] = {}
        self._hash_image_r_to_preimage: Dict[int, str] = {}
        self._channels: Dict[str, cm.Channel] = {}
        self._locked_funds: int = 0
        self._locked_funds_since_block: int = 0
        self._base_fee = base_fee
        self._fee_percentage = fee_percentage
        self._griefing_penalty_rate = griefing_penalty_rate
        self._transaction_id_to_transaction_info: Dict[int, TransactionInfo] = {}
        self._transaction_id_to_final_node: Dict[int, 'LightningNode'] = {}
        self._transaction_id_to_forward_contracts: Dict[int, 'cn.ContractForward'] = {}
        self._transaction_id_to_cancellation_contracts: Dict[int, 'cn.ContractCancellation'] = {}
        self._transaction_id_to_htlc_contracts: Dict[int, 'cn.Contract_HTLC'] = {}
        self._delta = delta
        self._max_number_of_block_to_respond = max_number_of_block_to_respond
        self._is_victim = False

        BLOCKCHAIN_INSTANCE.add_node(self, balance)

    def set_as_victim(self):
        self._is_victim = True

    def set_base_fee(self, base_fee):
        self._base_fee = base_fee

    def set_fee_percentage(self, fee_percentage):
        self._fee_percentage = fee_percentage

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

    @property
    def base_fee(self):
        return self._base_fee

    def _get_log_prefix(self):
        return "Victim: " if self._is_victim else ""

    def log_avg_metric(self, key, value):
        METRICS_COLLECTOR_INSTANCE.average(self._get_log_prefix() + key, value)

    def log_sum_metric(self, key, value):
        METRICS_COLLECTOR_INSTANCE.sum(self._get_log_prefix() + key, value)

    def log_count_metric(self, key):
        METRICS_COLLECTOR_INSTANCE.count(self._get_log_prefix() + key)

    def get_capacity_left(self, other_node):
        """
        returns the capacity left in the channel between `self` and `other_node`.
        """
        if other_node.address in self._other_nodes_to_channels:
            channel = self._other_nodes_to_channels[other_node.address]
            return channel.amount_owner1_can_transfer_to_owner2 if channel.is_owner1(self) else \
                channel.amount_owner2_can_transfer_to_owner1

    def get_fee_for_transfer_amount(self, amount_in_mast: int) -> int:
        """
        returns the fee this node will consume for the given amount.
        """
        return self.base_fee + int(self._fee_percentage * amount_in_mast)

    def establish_channel(self, other_node: 'LightningNode', amount_in_msat: int, is_bad_channel=False) -> cm.Channel:
        """
        establishes a channel between this node and `other_node` and puts in the given amount.
        """
        channel_data = cm.ChannelData(self, other_node)
        default_split = cm.MessageState(amount_in_msat, 0)
        channel = other_node.notify_of_channel(channel_data, default_split, is_bad_channel)
        self._other_nodes_to_channels[other_node.address] = channel
        self._channels[channel_data.address] = channel

        return channel

    def notify_of_channel(self, channel_data: cm.ChannelData, default_split: cm.MessageState, is_bad_channel: bool) -> cm.Channel:
        """
        Used for notifying this node of a channel being created.
        """
        channel = cm.Channel(channel_data, default_split, is_bad_channel)
        default_split.channel_address = channel_data.address
        self._other_nodes_to_channels[channel_data.owner1.address] = channel
        self._channels[channel_data.address] = channel
        return channel

    def add_money_to_channel(self, channel: cm.Channel, amount_in_mast: int):
        """
        Used to enable owner2 to add funds to a given channel.
        """
        channel.owner2_add_funds(amount_in_mast)

    def start_transaction(self, final_node: 'LightningNode', amount_in_msat, nodes_between: List['LightningNode']):
        """
        Start a transaction between this node and `final_node`.
        :param final_node: The node to send the money to.
        :param amount_in_msat: The amount to send.
        :param nodes_between: The path to take during the transaction.
        """
        hash_x, hash_r = final_node.generate_secret_x_hash(), final_node.generate_secret_r_hash()
        node_to_send = nodes_between[0]

        total_fee = self._calculate_fee_for_route(nodes_between[:-1], amount_in_msat)
        self.log_avg_metric(TOTAL_FEE, total_fee)

        id = TransactionInfo.generate_id()
        delta_waiting_time = ((len(nodes_between) + 1) * BLOCKS_IN_DAY)
        info = TransactionInfo(id, amount_in_msat + total_fee, 0, hash_x, hash_r,
                               BLOCKCHAIN_INSTANCE.block_number + delta_waiting_time, delta_waiting_time,
                               BLOCKCHAIN_INSTANCE.block_number, len(nodes_between), next_node=node_to_send)
        self._transaction_id_to_transaction_info[id] = info
        self._transaction_id_to_final_node[id] = final_node
        self.send_transaction_information(node_to_send, info, nodes_between[1:])

    @staticmethod
    def _calculate_fee_for_route(path_nodes: List['LightningNode'], amount_in_msat: int) -> int:
        transfer_amount = amount_in_msat
        for node in reversed(path_nodes):
            transfer_amount = (transfer_amount + node.base_fee) / (1 - node.fee_percentage)
        return int(round(transfer_amount) - amount_in_msat)

    def _calculate_griefing_penalty(self, amount_in_msat: int, waiting_time):
        return int(self._griefing_penalty_rate * amount_in_msat * waiting_time * 10)

    def send_transaction_information(self, node_to_send: 'LightningNode', transaction_info: TransactionInfo,
                                     nodes_between: List['LightningNode']):
        """
        Sends a transaction information `transaction_info` to the next node `node_to_send` in the path `nodes_between`.
        """
        node_to_send.receive_transaction_information(self, transaction_info, nodes_between)

    def receive_transaction_information(self, sender: 'LightningNode', previous_transaction_info: TransactionInfo,
                                        nodes_between: List['LightningNode']):
        """
        Receives a transaction information `previous_transaction_info`, deduces it's own `TransactionInfo` from it and
        sends information (via `send_transaction_information`) to the next node in the path `nodes_between` if exists, otherwise
        starts sending cancellation contracts backwards in the path.
        """
        fee = self.get_fee_for_transfer_amount(previous_transaction_info.amount_in_msat)
        amount_in_msat = previous_transaction_info.amount_in_msat - fee
        waiting_time = previous_transaction_info.expiration_block_number - BLOCKS_IN_DAY
        delta_waiting_time = previous_transaction_info.delta_wait_time - BLOCKS_IN_DAY
        griefing_penalty = previous_transaction_info.penalty + \
                           self._calculate_griefing_penalty(previous_transaction_info.amount_in_msat, delta_waiting_time)

        if nodes_between:
            node_to_send = nodes_between[0]
            if type(node_to_send) == LightningNode:
                self.log_count_metric(TRANSACTIONS_PASSED_THROUGH)
            info = TransactionInfo(previous_transaction_info.id, amount_in_msat, griefing_penalty,
                                   previous_transaction_info.hash_x, previous_transaction_info.hash_r, waiting_time,
                                   delta_waiting_time, previous_transaction_info.starting_block,
                                   previous_transaction_info.path_length, sender, node_to_send)
            self._transaction_id_to_transaction_info[previous_transaction_info.id] = info
            self.send_transaction_information(node_to_send, info, nodes_between[1:])
        else:
            info = TransactionInfo(previous_transaction_info.id, 0, griefing_penalty,
                                   previous_transaction_info.hash_x, previous_transaction_info.hash_r, waiting_time,
                                   delta_waiting_time, previous_transaction_info.starting_block,
                                   previous_transaction_info.path_length, sender)
            self._transaction_id_to_transaction_info[info.id] = info
            FUNCTION_COLLECTOR_INSTANCE.append(lambda: self._check_if_forward_contract_is_available(info.id),
                                               BLOCKCHAIN_INSTANCE.block_number + self._delta)
            self.send_cancellation_contract(info.id)

    def send_cancellation_contract(self, transaction_id: int):
        """
        Sends a cancellation contract to the previous node in the path of the transaction. All needed information is in the
        transaction information this node got when received it in `receive_transaction_information`, which corresponds to
        `transaction_id`.
        """
        assert transaction_id in self._transaction_id_to_transaction_info
        info = self._transaction_id_to_transaction_info[transaction_id]
        channel = self._other_nodes_to_channels[info.previous_node.address]

        cancellation_contract = cn.ContractCancellation(transaction_id, info.penalty, info.hash_x, info.hash_r,
                                                        info.expiration_block_number, channel, self, info.previous_node)
        self._transaction_id_to_cancellation_contracts[transaction_id] = cancellation_contract
        info.previous_node.receive_cancellation_contract(transaction_id, cancellation_contract)

    def receive_cancellation_contract(self, transaction_id: id, contract: 'cn.ContractCancellation'):
        """
        Receives the cancellation contract `contract` and accepts it if can be accepted. Uses the information that corresponds to
        `transaction_id` for calling the previous node in the transaction's path if exists, otherwise starts sending a forward
        contract.
        """
        info = self._transaction_id_to_transaction_info[transaction_id]

        if not contract.attached_channel.add_contract(contract):
            self.log_count_metric(ADD_CANCELLATION_CONTRACT_FAILED)
            return
        contract.accept_contract()

        if info.previous_node is not None:
            self.send_cancellation_contract(transaction_id)
        else:
            self.send_forward_contract(transaction_id)

    def _check_if_forward_contract_is_available(self, transaction_id: int):
        if transaction_id not in self._transaction_id_to_cancellation_contracts or \
                transaction_id in self._transaction_id_to_forward_contracts:
            return

        info = self._transaction_id_to_transaction_info[transaction_id]
        r = self._hash_image_r_to_preimage[info.hash_r]
        self.terminate_transaction(transaction_id, r)

    def send_forward_contract(self, transaction_id: int):
        """
        Sends a forward contract to the next node in the path of the transaction. All needed information is in the
        transaction information this node got when received it in `receive_transaction_information`, which corresponds to
        `transaction_id`.
        """
        assert transaction_id in self._transaction_id_to_transaction_info

        info = self._transaction_id_to_transaction_info[transaction_id]
        channel = self._other_nodes_to_channels[info.next_node.address]

        forward_contract = cn.ContractForward(transaction_id, info.amount_in_msat, info.hash_x, info.hash_r,
                                              info.expiration_block_number, channel, self, info.next_node)
        self._transaction_id_to_forward_contracts[transaction_id] = forward_contract
        info.next_node.receive_forward_contract(transaction_id, forward_contract)

    def receive_forward_contract(self, transaction_id: int, contract: 'cn.ContractForward'):
        """
        Receives the forward contract `contract` and accepts it if can be accepted. Uses the information that corresponds to
        `transaction_id` for calling the next node in the transaction's path if exists, otherwise starts resolving the
        transaction with the previous node in the path.
        """
        if transaction_id not in self._transaction_id_to_transaction_info:
            return
        info = self._transaction_id_to_transaction_info[transaction_id]

        if not contract.attached_channel.add_contract(contract):
            self.log_count_metric(ADD_FORWARD_CONTRACT_FAILED)
            return
        contract.accept_contract()

        if info.next_node is not None:
            self.send_forward_contract(transaction_id)
        else:
            self._resolve_transaction_after_receiving_forward_contract(info)

    def _resolve_transaction_after_receiving_forward_contract(self, transaction_info: 'TransactionInfo'):
        x = self._hash_image_x_to_preimage[transaction_info.hash_x]
        del self._hash_image_x_to_preimage[transaction_info.hash_x]
        self.resolve_transaction(transaction_info.id, x)

    @random_delay_node
    def resolve_transaction(self, transaction_id: int, x: str):
        """
        Settles the contracts that correspond to the given `transaction_id` with the given pre image `x` and calls
        `resolve_transaction` on the previous node in the transaction path if exists.
        """
        if transaction_id not in self._transaction_id_to_transaction_info:
            return  # might get terminated beforehand
        info = self._transaction_id_to_transaction_info[transaction_id]

        if info.next_node is not None and transaction_id in self._transaction_id_to_forward_contracts:
            forward_contract = self._transaction_id_to_forward_contracts[transaction_id]
            del self._transaction_id_to_forward_contracts[transaction_id]
            if forward_contract.is_expired:
                return
            forward_contract.report_x(x)
            self.log_count_metric(TRANSACTIONS_PASSED_SUCCESSFUL)

        if info.previous_node is None:
            del self._transaction_id_to_final_node[info.id]
            self.log_count_metric(TRANSACTION_SUCCESSFUL_COUNT)
            self.log_avg_metric(TRANSACTION_WAITING_TIME_BEFORE_COMPLETING,
                                BLOCKCHAIN_INSTANCE.block_number - info.starting_block)
            return

        if transaction_id not in self._transaction_id_to_cancellation_contracts:
            return
        cancellation_contract = self._transaction_id_to_cancellation_contracts[transaction_id]
        del self._transaction_id_to_cancellation_contracts[transaction_id]
        if cancellation_contract.is_expired:
            return
        cancellation_contract.report_x(x)

        if transaction_id in self._transaction_id_to_transaction_info:
            del self._transaction_id_to_transaction_info[transaction_id]

        info.previous_node.resolve_transaction(transaction_id, x)

    def terminate_transaction(self, transaction_id: int, r: str):
        """
        Terminates the contracts that correspond to the given `transaction_id` with the given pre image `r` and calls
        `resolve_transaction` on the previous node in the transaction path if exists.
        """
        if transaction_id not in self._transaction_id_to_transaction_info:
            return
        info = self._transaction_id_to_transaction_info[transaction_id]
        if type(self) == LightningNode and info.next_node is None:
            self.log_count_metric(TERMINATE_TRANSACTION)

        if transaction_id in self._transaction_id_to_forward_contracts:
            forward_contract = self._transaction_id_to_forward_contracts[transaction_id]
            del self._transaction_id_to_forward_contracts[transaction_id]
            if forward_contract.is_expired or not forward_contract.is_valid:
                return
            forward_contract.report_r(r)

        if info.previous_node is None:
            return

        cancellation_contract = self._transaction_id_to_cancellation_contracts[transaction_id]
        del self._transaction_id_to_cancellation_contracts[transaction_id]
        if cancellation_contract.is_expired or not cancellation_contract.is_valid:
            return
        cancellation_contract.report_r(r)

        del self._transaction_id_to_transaction_info[transaction_id]
        info.previous_node.terminate_transaction(transaction_id, r)

    def start_regular_htlc_transaction(self, final_node: 'LightningNode', amount_in_msat: int,
                                       nodes_between: List['LightningNode']):
        """
        Starts a transaction between `self` and `final_node` with the original ('regular') htlc protocol. Creates a transaction
        info and sends it to the next node in the path `nodes_between`
        """
        hash_x = final_node.generate_secret_x_hash()
        assert nodes_between
        node_to_send = nodes_between[0]
        total_fee = self._calculate_fee_for_route(nodes_between[:-1], amount_in_msat)
        self.log_avg_metric(TOTAL_FEE, total_fee)

        id = TransactionInfo.generate_id()
        delta_waiting_time = ((len(nodes_between) + 1) * BLOCKS_IN_DAY)
        info = TransactionInfo(id, amount_in_msat + total_fee, 0, hash_x, 0, BLOCKCHAIN_INSTANCE.block_number + delta_waiting_time,
                               delta_waiting_time, BLOCKCHAIN_INSTANCE.block_number, len(nodes_between), next_node=node_to_send)
        self._transaction_id_to_transaction_info[id] = info
        self.send_regular_htlc(info, nodes_between[1:])

    def send_regular_htlc(self, transaction_info: TransactionInfo, nodes_between: List['LightningNode']):
        """
        Creates a forward contract (which acts as a regular htlc) `ContractForward` and sends it with the
        current `TransactionInfo` to the `next_node` in `transaction_info`
        """
        channel = self._other_nodes_to_channels[transaction_info.next_node.address]

        contract = cn.ContractForward(transaction_info.id, transaction_info.amount_in_msat, transaction_info.hash_x, 0,
                                      transaction_info.expiration_block_number, channel, self, transaction_info.next_node)
        transaction_info.next_node.receive_regular_htlc(self, transaction_info, contract, nodes_between)

    def receive_regular_htlc(self, sender: 'LightningNode', previous_transaction_info: TransactionInfo,
                             contract: 'cn.Contract_HTLC', nodes_between: List['LightningNode']):
        """
        Receives a forward contract from `sender`, uses `previous_transaction_info` to deduce it's own `TransactionInfo` and sends
        a new contract to the next node in `nodes_between` if exists, otherwise starts resolving the transaction with the
        previous node.
        """
        node_to_send = nodes_between[0] if nodes_between else None
        fee = self.get_fee_for_transfer_amount(previous_transaction_info.amount_in_msat)
        amount_in_msat = previous_transaction_info.amount_in_msat - fee if nodes_between else 0
        delta_waiting_time = previous_transaction_info.delta_wait_time - BLOCKS_IN_DAY
        new_info = TransactionInfo(previous_transaction_info.id, amount_in_msat, 0, previous_transaction_info.hash_x, 0,
                                   previous_transaction_info.expiration_block_number - BLOCKS_IN_DAY, delta_waiting_time,
                                   previous_transaction_info.starting_block, previous_transaction_info.path_length,
                                   sender, node_to_send)

        self._transaction_id_to_transaction_info[new_info.id] = new_info
        self._transaction_id_to_htlc_contracts[new_info.id] = contract
        if not contract.attached_channel.add_contract(contract):
            return
        contract.accept_contract()

        if nodes_between:
            self.log_count_metric(TRANSACTIONS_PASSED_THROUGH)
            self.send_regular_htlc(new_info, nodes_between[1:])
        else:
            x = self._hash_image_x_to_preimage[new_info.hash_x]
            self.resolve_htlc_transaction(new_info.id, x)

    @random_delay_node
    def resolve_htlc_transaction(self, transaction_id: int, x: str):
        """
        Resolves the transaction the corresponds to `transaction_id` with the given pre-image `x`.
        """
        if transaction_id not in self._transaction_id_to_transaction_info:
            return
        info = self._transaction_id_to_transaction_info[transaction_id]
        del self._transaction_id_to_transaction_info[transaction_id]

        if info.previous_node is not None:
            contract = self._transaction_id_to_htlc_contracts[transaction_id]
            del self._transaction_id_to_htlc_contracts[transaction_id]
            if contract.is_expired:
                return
            contract.report_x(x)
            self.log_count_metric(TRANSACTIONS_PASSED_SUCCESSFUL)
        else:
            self.log_count_metric(TRANSACTION_SUCCESSFUL_COUNT)
            self.log_avg_metric(TRANSACTION_WAITING_TIME_BEFORE_COMPLETING,
                                BLOCKCHAIN_INSTANCE.block_number - info.starting_block)
            return

        info.previous_node.resolve_htlc_transaction(transaction_id, x)

    def generate_secret_x_hash(self) -> int:
        """
        Generates a new random key `x` (acts as a transaction confirmation key) and returns it's hash.
        """
        x = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        hash_image = hash(x)
        self._hash_image_x_to_preimage[hash_image] = x
        return hash_image

    def generate_secret_r_hash(self) -> int:
        """
        Generates a new random key `r` (acts as a transaction cancellation key) and returns it's hash.
        """
        r = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        hash_image = hash(r)
        self._hash_image_r_to_preimage[hash_image] = r
        return hash_image

    def close_channel(self, node):
        """
        Closing the channel between `self` and `node`.
        """
        if node.address not in self._other_nodes_to_channels:
            return

        channel = self._other_nodes_to_channels[node.address]
        del self._other_nodes_to_channels[node.address]
        if channel.channel_state.channel_data.address not in self._channels:
            return
        channel.close_channel()

    def notify_of_change_in_locked_funds(self, locked_fund):
        """
        Used to notify this node of a change in its locked funds in one of its channels.
        """
        total_last_locked_fund = self._locked_funds * (BLOCKCHAIN_INSTANCE.block_number - self._locked_funds_since_block)
        assert total_last_locked_fund >= 0
        if total_last_locked_fund > 0:
            self.log_sum_metric(TOTAL_LOCKED_FUND_IN_EVERY_BLOCKS, total_last_locked_fund)

        self._locked_funds += locked_fund
        self._locked_funds_since_block = BLOCKCHAIN_INSTANCE.block_number

    def notify_of_closed_channel(self, channel: 'cm.Channel', other_node: 'LightningNode'):
        """
        Used to notify this node that one of its channels closed.
        """
        if channel.channel_state.channel_data.address not in self._channels:
            return
        del self._channels[channel.channel_state.channel_data.address]

        if other_node.address in self._other_nodes_to_channels:
            del self._other_nodes_to_channels[other_node.address]

    def notify_of_cancellation_contract_payment(self, contract: 'cn.ContractCancellation'):
        """
        Used to notify this node of cancellation contract payment and to close this chain of cancellation contract off-chain.
        """
        info = self._transaction_id_to_transaction_info[contract.transaction_id]

        previous_node = info.previous_node
        if previous_node is None:
            return

        channel = self._other_nodes_to_channels[previous_node.address]

        if info.id not in self._transaction_id_to_cancellation_contracts:
            return
        previous_contract = self._transaction_id_to_cancellation_contracts[info.id]
        if not previous_contract.is_valid:
            return
        channel.pay_amount_to_owner(previous_contract)
        contract.invalidate()
        previous_node.notify_of_cancellation_contract_payment(previous_contract)


class LightningNodeAttacker(LightningNode):
    def __init__(self, *args, block_amount_to_send_transaction: int):
        super(LightningNodeAttacker, self).__init__(*args)
        self._node_to_attack: Optional['LightningNode'] = None
        self._peer: Optional['LightningNode'] = None
        self._block_amount_to_send_transaction = block_amount_to_send_transaction

    def _get_log_prefix(self):
        return "Attacker: "

    def get_victim(self):
        return self._node_to_attack

    def set_victim(self, node: 'LightningNode'):
        self._node_to_attack = node

    def get_peer(self):
        return self._peer

    def set_peer(self, peer: 'LightningNode'):
        self._peer = peer

    def should_send_attack(self) -> bool:
        return BLOCKCHAIN_INSTANCE.block_number % self._block_amount_to_send_transaction == 0

    def how_much_to_send(self):
        return 100000


class LightningNodeSoftGriefing(LightningNodeAttacker):
    def __init__(self, *args, block_amount_to_send_transaction: int):
        super(LightningNodeSoftGriefing, self).__init__(*args, block_amount_to_send_transaction=block_amount_to_send_transaction)
        self._block_number_to_resolve = 50

    def _resolve_transaction_after_receiving_forward_contract(self, transaction_info: 'TransactionInfo'):
        """
        This function only called when attacking, so use function collector to terminate the transaction in the latest time.
        """
        r = self._hash_image_r_to_preimage[transaction_info.hash_r]
        blocks_to_wait = transaction_info.expiration_block_number - \
                         (transaction_info.path_length * self._block_amount_to_send_transaction)
        assert blocks_to_wait > 0
        FUNCTION_COLLECTOR_INSTANCE.append(lambda: super(LightningNodeSoftGriefing, self)
                                           .terminate_transaction(transaction_info.id, r),
                                           BLOCKCHAIN_INSTANCE.block_number + blocks_to_wait)


class LightningNodeDosAttack(LightningNodeAttacker):
    def __init__(self, *args, block_amount_to_send_transaction: int):
        super(LightningNodeDosAttack, self).__init__(*args, block_amount_to_send_transaction=block_amount_to_send_transaction)

    def receive_cancellation_contract(self, transaction_id: id, contract: 'cn.ContractCancellation'):
        """
        Ignore messages from the node_to_attack, otherwise, ack normal.
        """
        if self._transaction_id_to_final_node.get(transaction_id) == self._node_to_attack:
            return
        else:
            super(LightningNodeDosAttack, self).receive_cancellation_contract(transaction_id, contract)
