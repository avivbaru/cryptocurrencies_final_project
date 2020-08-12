import time
from typing import Dict, List, Tuple, Set
import random
import string
from Contract_HTLC import *
from ChannelManager import *
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
    def __init__(self):
        """
        Initializes a new node that uses the given local ethereum account to move money
        :param my_account: The account's address.
        """
        self._address = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self._other_nodes_to_channels: Dict[str, ChannelManager] = {}
        self._hash_image_to_preimage: Dict[int, str] = {}
        self._channels: Dict[str, ChannelManager] = {}
        # TODO: check if we need all these dicts or just pass on the channel managers

    @property
    def address(self):
        """
        Returns the address of this node.
        """
        return self._address

    def establish_channel(self, other_party: LightningNode, amount_in_wei: int) -> ChannelManager:
        """
        Sets up a channel with another user at the given ethereum address.
        Returns the address of the contract on the blockchain.
        :param other_party_address: the other channel member
        :param amount_in_wei: the amount to send to the channel
        :return: returns the contract address on the blockchain
        """
        channel_data = ChannelData(self.address, other_party.address)
        default_split = MessageState(amount_in_wei, 0)
        channel = other_party.notify_of_channel(channel_data, default_split)
        self._other_nodes_to_channels[other_party.address] = channel
        self._channels[channel_data.address] = channel

        Blockchain.BLOCKCHAIN_INSTANCE.add_channel(channel)
        return channel

    def notify_of_channel(self, channel_data: ChannelData, default_split: MessageState) -> ChannelManager:
        """
        A function that is called when someone created a channel with you and wants to let you know.
        :param contract_address: channel address
        """
        channel = ChannelManager(channel_data, default_split)
        self._other_nodes_to_channels[channel_data.owner1] = channel
        self._channels[channel_data.address] = channel
        return channel

    def add_money_to_channel(self, channel: ChannelManager, amount_in_wei: int):
        channel.owner2_add_funds(amount_in_wei)

    def start_htlc(self, amount_in_wei, final_node: 'LightningNode', nodes_between: List[LightningNode]):
        """
        Sends money to the other address in the channel, and notifies the other node (calling its recieve()).
        :param contract_address: the channel address
        :param amount_in_wei: the amount to send to the other account
        :param other_node: the other account node
        """
        hash_image = final_node.generate_secret_x()
        node_to_send = nodes_between[0] if nodes_between else final_node
        # TODO: add fee
        message_state = self._get_message_state_for_sending_money(amount_in_wei, node_to_send)
        htlc_contract = Contract_HTLC(message_state, hash_image, len(nodes_between) + 1)  # TODO: see if this is a good time
        # for htlc maybe pass time in argument

        self.send_htlc(node_to_send, amount_in_wei, h_of_x, nodes_between)

    def _get_message_state_for_sending_money(self, amount_in_wei: int, node_to_send: LightningNode) -> MessageState:
        channel: ChannelManager = self._other_nodes_to_channels[node_to_send.address]
        new_serial_number = channel.channel_state.message_state.serial_number + 1
        current_owner1_balance = channel.channel_state.message_state.owner1_balance
        assert(current_owner1_balance + amount_in_wei <= channel.amount_owner1_can_transfer_to_owner2)  # TODO: put more asserts in code!!!
        if channel.channel_state.channel_data.owner1 == self.address:
            return MessageState(current_owner1_balance + amount_in_wei, new_serial_number)
        assert(current_owner1_balance - amount_in_wei >= 0)
        return MessageState(current_owner1_balance + amount_in_wei, new_serial_number)


    def send_htlc(self, node_to_send, amount_in_wei, h_of_x, nodes_between):
        channel_state = self._other_nodes_to_channels[node_to_send.get_address()]
        other_new_balance, serial = self._get_other_new_balance_and_serial(channel_state, amount_in_wei)

        new_message_state = ChannelMessageHTLC(node_to_send.get_address(), other_new_balance,
                                               serial, channel_state.channel_data.address,
                                               h_of_x, self._blockchain._block_number, len(nodes_between) + 1)
        node_to_send.receive_htlc(new_message_state, nodes_between[1:], amount_in_wei)

    def receive_htlc(self, state_msg: ChannelMessageHTLC, nodes_between: List[
        'LightningNode'], amount_in_wei):
        channel_state = self._channels[state_msg.channel_address]
        channel_state.message_htlc = state_msg
        if nodes_between:
            node_to_send = nodes_between[0]
            self.send_htlc(node_to_send, amount_in_wei, state_msg.h_of_x, nodes_between[1:])

    def generate_secret_x(self):
        x = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self._hash_image_to_preimage[hash(x)] = x
        return hash(x)

    def _get_other_new_balance_and_serial(self, channel_state, amount_in_wei):
        channel_data = channel_state.channel_data
        last_message_state = channel_state.message_state
        other_new_balance = channel_data.owner2_balance if channel_data.owner1 == self._account_address else \
            channel_data.owner1_balance
        other_new_balance += amount_in_wei
        serial = STARTING_SERIAL
        if last_message_state is not None:
            serial = last_message_state.serial + 1
            other_new_balance = channel_data.total_wei - last_message_state.balance + amount_in_wei
        return other_new_balance, serial

    def close_channel(self, channel_address):
        """
        Closes the channel at the given contract address.
        :param contract_address: channel address
        :param channel_state: this is the latest state which is signed by the other node, or None,
        if the channel is to be closed using its current balance allocation.
        """
        self._blockchain.close_channel(self._channels[channel_address].message_state)

    def close_channel_htlc(self, channel_address):
        """
        Closes the channel at the given contract address.
        :param contract_address: channel address
        :param channel_state: this is the latest state which is signed by the other node, or None,
        if the channel is to be closed using its current balance allocation.
        """
        if self._channels[channel_address].message_htlc:
            message_htlc = self._channels[channel_address].message_htlc
            self._blockchain.close_channel_htlc(message_htlc, self._hash_image_to_preimage[message_htlc.h_of_x])


    def find_secret_x(self, channel_closed):
        secret_x = self._blockchain.get_closed_channel_secret_x(channel_closed)
        self._hash_image_to_preimage[hash(secret_x)] = secret_x

