import contract_htlc as cn
import lightning_node as lc
import channel_manager as cm
from typing import Dict


class BlockChain:
    def __init__(self):
        self.init_parameters()

    def init_parameters(self):
        self._block_number = 0
        self._open_channels: Dict[str, 'cm.ChannelManager'] = {}
        self._channels_to_htlcs: Dict[str, 'cn.Contract_HTLC'] = {}
        self._nodes_addresses_to_balances: Dict[str, int] = {}
        self._fee = 0.1

    @property
    def block_number(self):
        return self._block_number

    def get_balance_for_node(self, node):
        return self._nodes_addresses_to_balances.get(node.address)

    @property
    def fee(self):
        return self._fee
    # TODO: maybe use and check before making a transaction

    def wait_k_blocks(self, k):
        for i in range(k):
            self._block_number += 1
            # notify all of block mined

        # TODO: maybe make this not immediate (one by one)
        # can have a subscribe method that calls all objects that called it with a new state (every time)

    def add_channel(self, channel: 'cm.ChannelManager'):
        self.apply_transaction(channel.channel_state.channel_data.owner1, channel.channel_state.message_state.owner1_balance)
        self._open_channels[channel.channel_state.channel_data.address] = channel

    def close_channel(self, message_state: 'cn.MessageState'):
        if message_state.channel_address not in self._open_channels:
            return # TODO: if we resolve all contracts of a closing channel, there is no need for this!!
        channel: cm.ChannelManager = self._open_channels[message_state.channel_address]
        owner2_balance = channel.channel_state.channel_data.total_wei - message_state.owner1_balance
        self._nodes_addresses_to_balances[channel.channel_state.channel_data.owner1.address] += \
            message_state.owner1_balance * (1 - self._fee)
        self._nodes_addresses_to_balances[channel.channel_state.channel_data.owner2.address] += owner2_balance * (1 - self._fee)
        # TODO: subtract transactions fee

        del self._open_channels[message_state.channel_address]
        # if contract:
        #     self._channels_to_htlcs[message_state.channel_address] = contract

    def add_node(self, node: 'lc.LightningNode', balance: int):
        if node.address in self._nodes_addresses_to_balances:
            return

        self._nodes_addresses_to_balances[node.address] = balance

    # def resolve_htlc_contract(self, contract: 'cn.Contract_HTLC'):
    #     owner1 = contract.attached_channel.channel_state.channel_data.owner1
    #     owner2 = contract.attached_channel.channel_state.channel_data.owner2
    #     balance_delta = contract.owner1_balance_delta
    #
    #     self._nodes_addresses_to_balances[owner1] += balance_delta
    #     self._nodes_addresses_to_balances[owner2] -= balance_delta

        # self._channels_to_htlcs[contract.attached_channel.channel_state.channel_data.address] = contract

    # def get_closed_channel_secret_x(self, channel_address):
    #     # TODO: one channel can have many htlcs
    #     if channel_address in self._channels_to_htlcs:
    #         return self._channels_to_htlcs[channel_address].pre_image

    def apply_transaction(self, node: 'lc.LightningNode', amount_in_wei: int):
        # TODO: figure out how to make owner2 put in funds in a nice way
        self._nodes_addresses_to_balances[node.address] -= amount_in_wei * (1 + self._fee)
        assert self._nodes_addresses_to_balances[node.address] >= 0

