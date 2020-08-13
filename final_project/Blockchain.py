from Contract_HTLC import *
from LightningChannel import *
from ChannelManager import ChannelManager


class BlockChain:
    def __init__(self):
        self._block_number = 0
        self._open_channels: Dict[str, ChannelManager] = {}
        self._channels_to_htlcs: Dict[str, 'Contract_HTLC'] = {}
        self._nodes_addresses_to_balances: Dict[str, int] = {}

    @property
    def block_number(self):
        return self._block_number

    def wait_k_blocks(self, k):
        for i in range(k):
            self._block_number += 1
            # notify all of block mined

        # TODO: maybe make this not immediate (one by one)
        # can have a subscribe method that calls all objects that called it with a new state (every time)

    def add_channel(self, channel: ChannelManager):
        # TODO: maybe call add cahnnel in channel init
        self._open_channels[channel.channel_state.channel_data.address] = channel

    def close_channel(self, message_state: 'MessageState', contract: 'Contract_HTLC' = None):
        channel: ChannelManager = self._open_channels[message_state.channel_address]
        owner2_balance = channel.channel_state.channel_data.total_wei - message_state.owner1_balance
        self._nodes_addresses_to_balances[channel.channel_state.channel_data.owner1] = message_state.owner1_balance
        self._nodes_addresses_to_balances[channel.channel_state.channel_data.owner2] = owner2_balance
        # TODO: subtract transactions fee

        del self._open_channels[message_state.channel_address]
        if contract:
            self._channels_to_htlcs[message_state.channel_address] = contract

    def add_node(self, node: 'LightningNode', balance: int):
        if node.address in self._nodes_addresses_to_balances:
            return

        self._nodes_addresses_to_balances[node.address] = balance

    def resolve_htlc_contract(self, contract: 'Contract_HTLC'):
        owner1 = contract.attached_channel.channel_state.channel_data.owner1
        owner2 = contract.attached_channel.channel_state.channel_data.owner2
        balance_delta = contract.owner1_balance_delta

        self._nodes_addresses_to_balances[owner1] += balance_delta
        self._nodes_addresses_to_balances[owner2] -= balance_delta

        self._channels_to_htlcs[contract.attached_channel.channel_state.channel_data.address] = contract

    def get_closed_channel_secret_x(self, channel_address):
        # TODO: one channel can have many htlcs
        if channel_address in self._channels_to_htlcs:
            return self._channels_to_htlcs[channel_address].pre_image


BLOCKCHAIN_INSTANCE = BlockChain()
