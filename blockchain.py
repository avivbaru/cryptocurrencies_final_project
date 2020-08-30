import contract_htlc as cn
import lightning_node as lc
import channel_manager as cm
from typing import Dict, Optional


class BlockChain:
    def __init__(self):
        self.init_parameters()

    def init_parameters(self):
        self._block_number = 0
        self._open_channels: Dict[str, 'cm.Channel'] = {}
        self._channels_to_htlcs: Dict[str, 'cn.Contract_HTLC'] = {}
        self._nodes_addresses_to_balances: Dict[str, int] = {}
        self._hash_image_to_pre_images: Dict[int, str] = {}
        self._fee = 0.1

    @property
    def block_number(self):
        return self._block_number

    @property
    def total_balance(self) -> int:
        return int(sum(self._nodes_addresses_to_balances.values()))  # TODO: maybe don't calculate for all nodes each time -
        # but keep an updating variable

    @property
    def fee(self):
        return self._fee

    def get_balance_for_node(self, node):
        return self._nodes_addresses_to_balances.get(node.address)

    def wait_k_blocks(self, k):
        self._block_number += 1

    def add_channel(self, channel: 'cm.Channel'):
        self.apply_transaction(channel.channel_state.channel_data.owner1, channel.channel_state.message_state.owner1_balance)
        self._open_channels[channel.channel_state.channel_data.address] = channel

    def close_channel(self, message_state: 'cm.MessageState'):
        if message_state.channel_address not in self._open_channels:
            return # TODO: if we resolve all contracts of a closing channel, there is no need for this!!
        channel: cm.Channel = self._open_channels[message_state.channel_address]
        owner2_balance = channel.channel_state.channel_data.total_wei - message_state.owner1_balance
        self._nodes_addresses_to_balances[channel.channel_state.channel_data.owner1.address] += \
            message_state.owner1_balance * (1 - self._fee)
        self._nodes_addresses_to_balances[channel.channel_state.channel_data.owner2.address] += owner2_balance * (1 - self._fee)

        del self._open_channels[message_state.channel_address]
        # if contract:
        #     self._channels_to_htlcs[message_state.channel_address] = contract

    def report_pre_image(self, hash_image: int, pre_image: str):
        self._hash_image_to_pre_images[hash_image] = pre_image

    def add_node(self, node: 'lc.LightningNode', balance: int):
        if node.address in self._nodes_addresses_to_balances:
            return

        self._nodes_addresses_to_balances[node.address] = balance

    def get_pre_image_if_exists_onchain(self, hash_image: int) -> Optional[str]:
        if hash_image in self._hash_image_to_pre_images:
            return self._hash_image_to_pre_images[hash_image]
        return None

    def apply_transaction(self, node: 'lc.LightningNode', amount_in_wei: int):
        # TODO: figure out how to make owner2 put in funds in a nice way
        self._nodes_addresses_to_balances[node.address] -= amount_in_wei * (1 + self._fee)
        assert self._nodes_addresses_to_balances[node.address] >= 0

