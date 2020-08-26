from typing import Dict, List, Tuple, Callable, Optional, Set
import random
import string
import contract_htlc as cn
import contract_htlc_gp as cn_gp
import channel_manager as cm
from singletons import *


BLOCK_IN_DAY = 5

APPEAL_PERIOD = 3  # the appeal period in blocks.
STARTING_SERIAL = 0  # first serial number


class LightningNode:
    def __init__(self, balance: int, fee_percentage: float = 0.1, griefing_penalty_rate: float = 0.01):
        # TODO: check if has balance when creating channels
        self._address = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self._other_nodes_to_channels: Dict[str, cm.ChannelManager] = {}
        self._hash_image_to_preimage: Dict[int, str] = {}
        self._channels: Dict[str, cm.ChannelManager] = {}
        self._locked_funds: int = 0
        self._balance = balance
        self._fee_percentage = fee_percentage
        self._griefing_penalty_rate = griefing_penalty_rate  # TODO: maybe have this as an attribute of the blockchain
        self._pending_contracts: Set = set()

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

    def establish_channel(self, other_party: 'LightningNode', amount_in_wei: int) -> cm.ChannelManager:
        channel_data = cm.ChannelData(self, other_party)
        default_split = cn.MessageState(amount_in_wei, 0)
        channel = other_party.notify_of_channel(channel_data, default_split)
        self._other_nodes_to_channels[other_party.address] = channel
        self._channels[channel_data.address] = channel
        self._balance -= amount_in_wei

        return channel

    def notify_of_channel(self, channel_data: cm.ChannelData, default_split: cn.MessageState) -> cm.ChannelManager:
        channel = cm.ChannelManager(channel_data, default_split)
        self._other_nodes_to_channels[channel_data.owner1.address] = channel
        self._channels[channel_data.address] = channel
        return channel

    def add_money_to_channel(self, channel: cm.ChannelManager, amount_in_wei: int):
        channel.owner2_add_funds(amount_in_wei)
        self._balance -= amount_in_wei

    def start_htlc(self, final_node: 'LightningNode', amount_in_wei, nodes_between: List['LightningNode']):
        hash_image = final_node.generate_secret_x()  # TODO: make final_node = nodes_between[-1]?
        assert nodes_between
        node_to_send = nodes_between[0]
        assert node_to_send
        total_fee = self._calculate_fee_for_route(nodes_between[:-1], amount_in_wei)

        self.send_htlc(node_to_send, amount_in_wei + total_fee, hash_image, nodes_between[1:], BLOCKCHAIN_INSTANCE.block_number
                       + ((len(nodes_between) + 1) * 144))  # TODO: returning true here has no meaning - should call simulation
        # with success
            # print("Transaction failed - WHAT TO DO NOW??? MY LIFE IS OVER")
            # return False

    def _calculate_fee_for_route(self, path_nodes: List['LightningNode'], amount_in_wei: int) -> int:
        transfer_amount = amount_in_wei
        for node in reversed(path_nodes):
            transfer_amount += node.get_fee_for_transfer_amount(transfer_amount)
        return transfer_amount - amount_in_wei

    def _calculate_griefing_penalty(self, amount_in_wei: int, waiting_time):
        return self._griefing_penalty_rate * amount_in_wei * waiting_time * 10
    # TODO: time = exp_time - current_block_number... though current block number may vary between nodes

    def send_htlc(self, node_to_send: 'LightningNode', amount_in_wei: int, hash_image: int,
                  nodes_between: List['LightningNode'], expiration_time: int, cumulative_griefing_penalty: int = 0):
        assert node_to_send
        channel = self._other_nodes_to_channels[node_to_send.address]
        assert channel
        delta_amount = self._get_delta_for_sending_money(amount_in_wei, channel)

        htlc_contract = cn_gp.Contract_HTLC_GP(delta_amount, hash_image,
                                               expiration_time, channel, self, node_to_send,
                                               cumulative_griefing_penalty +
                                               self._calculate_griefing_penalty(amount_in_wei, expiration_time -
                                                                                BLOCKCHAIN_INSTANCE.block_number))
        # TODO: maybe have a factory for creating HTLC vs HTLC-GP
        # TODO: maybe have the htlc not active till second owner calls a specific function
        self._pending_contracts.add(htlc_contract)
        node_to_send.receive_htlc(self, htlc_contract, amount_in_wei, nodes_between)

    def _get_delta_for_sending_money(self, amount_in_wei: int, channel: cm.ChannelManager) -> int:
        current_owner1_balance = channel.channel_state.message_state.owner1_balance
        current_owner2_balance = channel.channel_state.channel_data.total_wei - \
                                 channel.channel_state.message_state.owner1_balance
        if channel.channel_state.channel_data.owner1.address == self.address:
            assert (current_owner1_balance - amount_in_wei >= 0)  # TODO: put more
            # asserts in code!!!
            return -amount_in_wei
        else:
            assert(current_owner2_balance - amount_in_wei >= 0)
            return amount_in_wei

    def receive_htlc(self, sender: 'LightningNode', contract: cn.Contract_HTLC, amount_in_wei: int,
                     nodes_between: List['LightningNode'], cumulative_griefing_penalty: int = 0):
        contract.attached_channel.add_htlc_contract(contract)
        sender.accept_contract(contract)
        if nodes_between:
            node_to_send = nodes_between[0]
            fee = self.get_fee_for_transfer_amount(amount_in_wei)
            self.send_htlc(node_to_send, amount_in_wei - fee, contract.hash_image, nodes_between[1:],
                           contract.expiration_block_number - 1, cumulative_griefing_penalty)
        elif contract.hash_image in self._hash_image_to_preimage:
            self._start_resolving_contract_off_chain(sender, contract)
        assert False

    def accept_contract(self, contract: cn.Contract_HTLC):
        assert contract in self._pending_contracts
        self._pending_contracts.remove(contract)
        contract.accept(self)

    def decline_contract(self, contract: cn.Contract_HTLC):
        assert contract in self._pending_contracts
        self._pending_contracts.remove(contract)
        other_contract = self._find_other_contract_with_same_pre_image(contract.hash_image, contract.attached_channel)
        other_contract.owner1.terminate_contract(other_contract)

    def terminate_contract(self, contract: cn.Contract_HTLC):
        other_contract = self._find_other_contract_with_same_pre_image(contract.hash_image, contract.attached_channel)
        other_contract.owner1.terminate_contract(other_contract)  # TODO: finish this function, also add terminate in contract

    def _start_resolving_contract_off_chain(self, sender: 'LightningNode', contract: cn.Contract_HTLC):
        assert contract not in self._pending_contracts
        contract.resolve_offchain(self._hash_image_to_preimage[contract.hash_image])
        sender.notify_of_resolve_htlc_offchain(contract)

    def generate_secret_x(self):
        x = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self._hash_image_to_preimage[hash(x)] = x
        return hash(x)

    def close_channel(self, node):
        if node.address not in self._other_nodes_to_channels:
            return

        channel = self._other_nodes_to_channels[node.address]
        assert channel
        channel.close_channel()
        self._balance += channel.owner1_balance if channel.is_owner1(self) else channel.owner2_balance
        del self._channels[channel.channel_state.channel_data.address]
        del self._other_nodes_to_channels[node.address]

    def close_channel_htlc(self, contract: cn.Contract_HTLC):
        if contract.attached_channel not in self._channels or contract.pre_image not in self._hash_image_to_preimage:
            return

        contract.resolve_onchain(self._hash_image_to_preimage[contract.pre_image])
        del self._channels[contract.attached_channel.channel_state.channel_data.address]
        other_node = contract.attached_channel.channel_state.channel_data.owner2 if \
            contract.attached_channel.is_owner1(self) else \
            contract.attached_channel.channel_state.channel_data.owner1
        del self._other_nodes_to_channels[other_node.address]

    def find_pre_image(self, channel_closed: cm.ChannelManager):
        pre_image = BLOCKCHAIN_INSTANCE.get_closed_channel_secret_x(channel_closed)
        self._hash_image_to_preimage[hash(pre_image)] = pre_image
        return pre_image

    def notify_of_resolve_htlc_onchain(self, contract: cn.Contract_HTLC):
        if contract.attached_channel.channel_state.channel_data.address not in self._channels:
            return

        # pre_image = self.find_pre_image(contract.attached_channel) TODO: no real need for this one
        contract.attached_channel.resolve_htlc(contract)
        contract.attached_channel.close_channel()  # TODO: what else should do here?
        del self._channels[contract.attached_channel.channel_state.channel_data.address]
        other_contract: cn.Contract_HTLC = self._find_other_contract_with_same_pre_image(contract.hash_image,
                                                                                         contract.attached_channel)
        if other_contract is not None:
            other_contract.resolve_onchain(contract.pre_image)

    def _find_other_contract_with_same_pre_image(self, hash_image: int,
                                                 other_channel: cm.ChannelManager) -> Optional[cn.Contract_HTLC]:
        for channel in self._channels.values():
            if channel == other_channel:
                continue
            for htlc_contract in channel.channel_state.htlc_contracts:
                if htlc_contract.hash_image == hash_image:
                    return htlc_contract
        return None

    def notify_of_resolve_htlc_offchain(self, contract: cn.Contract_HTLC):
        if contract.attached_channel.channel_state.channel_data.address not in self._channels:
            return

        contract.attached_channel.resolve_htlc(contract)
        other_contract: cn.Contract_HTLC = self._find_other_contract_with_same_pre_image(contract.hash_image,
                                                                                         contract.attached_channel)
        # TODO: maybe have the owners inside the htlc_contracts so to not have this shit
        if other_contract is not None:
            other_contract.resolve_offchain(contract.pre_image)
            other_node = other_contract.owner2 if other_contract.owner1.address == self.address else other_contract.owner1
            self._notify_other_node_of_resolving_contract(other_node, other_contract)

    def _notify_other_node_of_resolving_contract(self, other_node: 'LightningNode', contract: cn.Contract_HTLC):
        other_node.notify_of_resolve_htlc_offchain(contract)

    def notify_of_griefed_contract(self, contract: cn.Contract_HTLC):
        other_contract: cn.Contract_HTLC = self._find_other_contract_with_same_pre_image(contract.hash_image,
                                                                                         contract.attached_channel)
        if other_contract is not None:
            other_node = other_contract.owner1
            assert self.address == other_contract.owner2.address
            other_node.notify_of_griefed_contract(other_contract)

    def notify_of_change_in_locked_funds(self, locked_fund):
        self._locked_funds += locked_fund


class LightningNodeGriefing(LightningNode):
    def __init__(self, balance: int, fee_percentage: float = 0.1, griefing_penalty_rate: float = 0.01):
        super().__init__(balance, fee_percentage, griefing_penalty_rate)

    def _start_resolving_contract_off_chain(self, sender: 'LightningNode', contract: cn.Contract_HTLC):
        return # this waits for expiration, classic griefing. below is "soft griefing"
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

    def _notify_other_node_of_resolving_contract(self, other_node: 'LightningNode', contract: cn.Contract_HTLC):
        return
        # target_block_number = contract.expiration_block_number - 1
        # FUNCTION_COLLECTOR_INSTANCE.append(
        #     self._collector_function_creator(target_block_number,
        #                                      lambda: super(LightningNodeGriefing, self)
        #                                      ._notify_other_node_of_resolving_contract(other_node, contract)))


class LightningNodeSoftGriefing(LightningNode):
    def __init__(self, balance: int, fee_percentage: float = 0.1, griefing_penalty_rate: float = 0.01):
        super().__init__(balance, fee_percentage, griefing_penalty_rate)

    def _start_resolving_contract_off_chain(self, sender: 'LightningNode', contract: cn.Contract_HTLC):
        target_block_number = contract.expiration_block_number - 1
        FUNCTION_COLLECTOR_INSTANCE.append(
            lambda: super(LightningNodeSoftGriefing, self).
                _start_resolving_contract_off_chain(sender, contract), target_block_number)

    def _collector_function_creator(self, func: Callable[[], None]) -> Callable[[], None]:
        def check_block_and_use_function():
            func()
        return check_block_and_use_function

    def _notify_other_node_of_resolving_contract(self, other_node: 'LightningNode', contract: cn.Contract_HTLC):
        target_block_number = contract.expiration_block_number - 1
        FUNCTION_COLLECTOR_INSTANCE.append(lambda: super(LightningNodeSoftGriefing, self)
                                           ._notify_other_node_of_resolving_contract(other_node, contract),
                                           target_block_number)


class LightningNodeReverseGriefing(LightningNode):
    def __init__(self, balance: int, fee_percentage: float = 0.1, griefing_penalty_rate: float = 0.01):
        super().__init__(balance, fee_percentage, griefing_penalty_rate)
        self._peers: List['LightningNodeReverseGriefing'] = []
        self._hash_to_peer: Dict[int, 'LightningNodeReverseGriefing'] = {}
        self._hash_to_grief: List[int] = []
        self._hash_to_not_accept_disable: List[int] = []

    @property
    def peers(self):
        return self._peers

    def _notify_of_peer(self, peer: 'LightningNodeReverseGriefing'):
        self._add_peers_from_new_peer(peer)
        peer._add_peers_from_new_peer(self)

    def _add_peers_from_new_peer(self, peer: 'LightningNodeReverseGriefing'):
        self._peers.append(peer)
        self._peers.extend(peer.peers)
        self._peers.remove(self)

    def _notify_peer_of_hash(self, hash: int):
        for peer in self._peers:
            peer._receive_contract_from_peer(hash, peer)

    def _notify_peer_of_hash_not_accept_disable(self, hash: int):
        self._hash_to_not_accept_disable.append(hash)

    def _receive_contract_from_peer(self, hash: int, peer: 'LightningNodeReverseGriefing'):
        self._hash_to_peer[hash] = peer

    def receive_htlc(self, sender: 'LightningNode', contract: cn.Contract_HTLC, amount_in_wei: int,
                     nodes_between: List['LightningNode'], cumulative_griefing_penalty: int = 0):
        if contract.hash_image in self._hash_to_peer:
            # Griefing!!!!!!
            # what happend if there is more then 2?????
            self._hash_to_peer[contract.hash_image]._notify_peer_of_hash_not_accept_disable(contract.hash_image)
            return
        self._notify_peer_of_hash(contract.hash_image)
        super().receive_htlc(sender, contract, amount_in_wei, nodes_between, cumulative_griefing_penalty)

    # TODO: complete!
    def decline_contract(self, contract: cn.Contract_HTLC):
        if contract.hash_image in self._hash_to_not_accept_disable:
            # getting money!!!!!
            return
        super().decline_contract(contract)

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