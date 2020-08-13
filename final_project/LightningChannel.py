import time
from typing import Dict, List, Tuple, Set, Optional
import random
import string
from Contract_HTLC import *
import ChannelManager as cm
import Blockchain

BLOCK_IN_DAY = 5

APPEAL_PERIOD = 3  # the appeal period in blocks.
STARTING_SERIAL = 0  # first serial number


def check_channel_address(func):
    """
    Decorator for Node method. Check if the Node know the channel address argument.
    """
    def wrapper(self, address, *args):
        if address in self._channels:
            return func(self, address, *args)

    return wrapper


class LightningNode:
    def __init__(self, balance: int):
        # TODO: check if has balance when creating channels
        self._address = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self._other_nodes_to_channels: Dict[str, cm.ChannelManager] = {}
        self._hash_image_to_preimage: Dict[int, str] = {}
        self._channels: Dict[str, cm.ChannelManager] = {}
        self._balance = balance
        Blockchain.BLOCKCHAIN_INSTANCE.add_node(self, balance)
        # TODO: check if we need all these dicts or just pass on the channel managers

    @property
    def address(self):
        """
        Returns the address of this node.
        """
        return self._address

    def get_capacity_left(self, other_node):
        if other_node.address in self._other_nodes_to_channels:
            return self._other_nodes_to_channels[other_node.address].amount_owner1_can_transfer_to_owner2 if  \
                self._other_nodes_to_channels[other_node.address].channel_state.channel_data.owner1.address == self.address else \
            self._other_nodes_to_channels[other_node.address].amount_owner2_can_transfer_to_owner1

    def establish_channel(self, other_party: 'LightningNode', amount_in_wei: int) -> cm.ChannelManager:
        channel_data = cm.ChannelData(self, other_party)
        default_split = MessageState(amount_in_wei, 0)
        channel = other_party.notify_of_channel(channel_data, default_split)
        self._other_nodes_to_channels[other_party.address] = channel
        self._channels[channel_data.address] = channel

        Blockchain.BLOCKCHAIN_INSTANCE.add_channel(channel)
        return channel

    def notify_of_channel(self, channel_data: cm.ChannelData, default_split: MessageState) -> cm.ChannelManager:
        channel = cm.ChannelManager(channel_data, default_split)
        self._other_nodes_to_channels[channel_data.owner1.address] = channel
        self._channels[channel_data.address] = channel
        return channel

    def add_money_to_channel(self, channel: cm.ChannelManager, amount_in_wei: int):
        channel.owner2_add_funds(amount_in_wei)

    def start_htlc(self, final_node: 'LightningNode', amount_in_wei, nodes_between: List['LightningNode']):
        hash_image = final_node.generate_secret_x()  # TODO: make fina;_node = nodes_between[-1]?
        assert nodes_between
        node_to_send = nodes_between[0]
        assert node_to_send
        # TODO: add fee

        if not self.send_htlc(node_to_send, amount_in_wei, hash_image, nodes_between[1:]):
            print("Transaction failed - WHAT TO DO NOW??? MY LIFE IS OVER")

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

    def send_htlc(self, node_to_send, amount_in_wei, hash_image, nodes_between) -> bool:
        assert node_to_send
        # TODO: add fee
        channel = self._other_nodes_to_channels[node_to_send.address]
        assert channel
        delta_amount = self._get_delta_for_sending_money(amount_in_wei, channel)

        htlc_contract = Contract_HTLC(delta_amount, hash_image, len(nodes_between) + 1,
                                      channel)  # TODO: see if this is a good time for htlc maybe pass time in argument
        return node_to_send.receive_htlc(htlc_contract, amount_in_wei, nodes_between)

    def receive_htlc(self, contract: Contract_HTLC, amount_in_wei: int, nodes_between: List['LightningNode']) -> bool:
        contract.attached_channel.add_htlc_contract(contract)
        if nodes_between:
            node_to_send = nodes_between[0]
            return self.send_htlc(node_to_send, amount_in_wei, contract.hash_image, nodes_between[1:])
        if contract.hash_image in self._hash_image_to_preimage:
            return contract.resolve_offchain(self._hash_image_to_preimage[contract.hash_image])

    def generate_secret_x(self):
        x = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self._hash_image_to_preimage[hash(x)] = x
        return hash(x)

    def close_channel(self, channel_address):
        if channel_address not in self._channels:
            return

        channel = self._channels[channel_address]
        assert channel
        channel.close_channel()
        del self._channels[channel.channel_state.channel_data.address]

    def close_channel_htlc(self, contract: Contract_HTLC):
        if contract.attached_channel not in self._channels or contract.pre_image not in self._hash_image_to_preimage:
            return

        contract.resolve_onchain(self._hash_image_to_preimage[contract.pre_image])
        del self._channels[contract.attached_channel.channel_state.channel_data.address]

    def find_pre_image(self, channel_closed: cm.ChannelManager):
        pre_image = Blockchain.BLOCKCHAIN_INSTANCE.get_closed_channel_secret_x(channel_closed)
        self._hash_image_to_preimage[hash(pre_image)] = pre_image
        return pre_image

    def notify_of_resolve_htlc_onchain(self, contract: Contract_HTLC):
        if contract.attached_channel.channel_state.channel_data.address not in self._channels:
            return

        # pre_image = self.find_pre_image(contract.attached_channel) TODO: no real need for this one
        contract.attached_channel.resolve_htlc(contract)
        contract.attached_channel.close_channel()  # TODO: what else should do here?
        del self._channels[contract.attached_channel.channel_state.channel_data.address]
        other_contract: Contract_HTLC = self._find_other_contract_with_same_pre_image(contract.hash_image,
                                                                                      contract.attached_channel)
        if other_contract is not None:
            other_contract.resolve_onchain(contract.pre_image)

    def _find_other_contract_with_same_pre_image(self, hash_image: int,
                                                 other_channel: cm.ChannelManager) -> Optional[Contract_HTLC]:
        for channel in self._channels.values():
            if channel == other_channel:
                continue
            for htlc_contract in channel.channel_state.htlc_contracts:
                if htlc_contract.hash_image == hash_image:
                    return htlc_contract
        return None

    def notify_of_resolve_htlc_offchain(self, contract: Contract_HTLC):
        if contract.attached_channel.channel_state.channel_data.address not in self._channels:
            return

        contract.attached_channel.resolve_htlc(contract)
        other_contract: Contract_HTLC = self._find_other_contract_with_same_pre_image(contract.hash_image,
                                                                                      contract.attached_channel)
        if other_contract is not None:
            other_contract.resolve_offchain(contract.pre_image)

