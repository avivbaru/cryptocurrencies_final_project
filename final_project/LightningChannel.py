import time
from typing import Dict, List, Tuple, Set
import random
import string

APPEAL_PERIOD = 3  # the appeal period in blocks.
STARTING_SERIAL = 0  # first serial number


class BlockChain:
    def __init__(self):
        self._block_number = 0
        self._open_channels: Dict[str, ChannelData] = {}
        self._closed_channels: Dict[str, Tuple[int, int, ChannelData]] = {}

    def wait_k_blocks(self, k):
        self._block_number += k

    def add_channel(self, channel):
        self._open_channels[channel.address] = channel

    def close_channel(self, message_state: 'ChannelMessage'):
        channel = self._open_channels[message_state.channel_address]
        other_balance = channel.total_wei - message_state.balance
        if message_state.owner_address == channel.owner1:
            channel.owner1_balance = message_state.balance
            channel.owner2_balance = other_balance
        else:
            channel.owner2_balance = message_state.balance
            channel.owner1_balance = other_balance
        del self._open_channels[message_state.channel_address]
        self._closed_channels[message_state.channel_address] = (self._block_number, message_state.serial,
                                                                channel)

    def close_channel_default_split(self, channel_address):
        channel = self._open_channels[channel_address]
        del self._open_channels[channel_address]
        self._closed_channels[channel_address] = (self._block_number, -1, channel)

    def appeal_closed_channel(self, message_state: 'ChannelMessage'):
        (block_number, serial, channel) = self._closed_channels[message_state.channel_address]
        if block_number + APPEAL_PERIOD > self._block_number and serial < message_state.serial:
            other_balance = channel.total_wei - message_state.balance
            if message_state.owner_address == channel.owner1:
                channel.owner1_balance = message_state.balance
                channel.owner2_balance = other_balance
            else:
                channel.owner2_balance = message_state.balance
                channel.owner1_balance = other_balance
            self._closed_channels[message_state.channel_address] = (self._block_number, message_state.serial,
                                                                    channel)

    def withdraw_fund(self, channel_address, account_address):
        # TODO: remove from dict?
        if self._closed_channels[channel_address][0] + APPEAL_PERIOD <= self._block_number:
            channel = self._closed_channels[channel_address][2]
            fund = channel.owner1_balance
            if channel.owner1 == account_address:
                channel.owner1_balance = 0
            else:
                fund = channel.owner2_balance
                channel.owner2_balance = 0
            return fund


class ChannelData:
    def __init__(self, owner1=None, owner2=None, total_wei=None):
        self.address = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self.owner1 = owner1
        self.owner2 = owner2
        self.owner1_balance = total_wei
        self.owner2_balance = 0
        self.total_wei = total_wei


class ChannelMessage:
    def __init__(self, owner_address, balance, serial, channel_address):
        self.owner_address = owner_address
        self.serial = serial
        # self.sig = sig
        # Assume balance is the amount of wei for the Node holding this message state
        self.balance = balance
        self.channel_address = channel_address


class ChannelState:
    def __init__(self, channel_data: ChannelData, message_state: ChannelMessage=None):
        self.channel_data: ChannelData = channel_data
        self.message_state: ChannelMessage = message_state


def check_channel_address(func):
    """
    Decorator for Node method. Check if the Node know the channel address argument.
    """
    def wrapper(self, address, *args):
        if address in self._channels:
            return func(self, address, *args)

    return wrapper


class LightningNode:
    def __init__(self, my_account, blockchain: BlockChain):
        """
        Initializes a new node that uses the given local ethereum account to move money
        :param my_account: The account's address.
        """
        self._account_address = my_account
        # TODO: change to dict to list
        self._other_nodes_to_channels: Dict[str, ChannelState] = {}
        self._channels: Dict[str, ChannelState] = {}
        self._blockchain = blockchain
        self._balance = 10

    def get_address(self):
        """
        Returns the address of this node on the blockchain (its ethereum wallet).
        """
        return self._account_address

    def establish_channel(self, other_party_address, amount_in_wei):
        """
        Sets up a channel with another user at the given ethereum address.
        Returns the address of the contract on the blockchain.
        :param other_party_address: the other channel member
        :param amount_in_wei: the amount to send to the channel
        :return: returns the contract address on the blockchain
        """
        self._balance -= amount_in_wei
        channel_data = ChannelData(self._account_address, other_party_address, amount_in_wei)
        self._blockchain.add_channel(channel_data)
        channel = ChannelState(channel_data)
        self._other_nodes_to_channels[other_party_address] = channel
        self._channels[channel_data.address] = channel
        return channel_data

    def notify_of_channel(self, channel_data: ChannelData, amount_in_wei):
        """
        A function that is called when someone created a channel with you and wants to let you know.
        :param contract_address: channel address
        """
        self._balance -= amount_in_wei
        channel_data.total_wei += amount_in_wei
        channel_data.owner2_balance = amount_in_wei
        channel = ChannelState(channel_data)
        self._other_nodes_to_channels[channel_data.owner1] = channel
        self._channels[channel_data.address] = channel

    def send(self, amount_in_wei, other_node: 'LightningNode', channel_address):
        """
        Sends money to the other address in the channel, and notifies the other node (calling its recieve()).
        :param contract_address: the channel address
        :param amount_in_wei: the amount to send to the other account
        :param other_node: the other account node
        """
        channel_state = self._channels[channel_address]
        channel_data = channel_state.channel_data
        last_message_state = channel_state.message_state
        other_new_balance = channel_data.owner2_balance if channel_data.owner1 == self._account_address else \
                            channel_data.owner1_balance
        other_new_balance += amount_in_wei
        serial = STARTING_SERIAL
        if last_message_state is not None:
            serial = last_message_state.serial + 1
            other_new_balance = channel_data.total_wei - last_message_state.balance + amount_in_wei

        new_message_state = ChannelMessage(other_node.get_address(), other_new_balance, serial, channel_address)
        returned_message_state = other_node.receive(new_message_state, self._account_address)
        channel_state.message_state = returned_message_state

    def receive(self, state_msg, other_node_address):
        """
        A function that is called when you've received funds.
        You are sent the message about the new channel state that is signed by the other user
        :param state_msg: the sign state from the other account
        :return: a state message with the signature of this node acknowledging the transfer.
        """
        channel_state = self._channels[state_msg.channel_address]
        other_balance = channel_state.channel_data.total_wei - state_msg.balance
        new_message_state = ChannelMessage(other_node_address, other_balance, state_msg.serial, state_msg.channel_address)
        channel_state.message_state = state_msg
        return new_message_state

    def close_channel(self, channel_address):
        """
        Closes the channel at the given contract address.
        :param contract_address: channel address
        :param channel_state: this is the latest state which is signed by the other node, or None,
        if the channel is to be closed using its current balance allocation.
        """
        if self._channels[channel_address].message_state:
            self._blockchain.close_channel(self._channels[channel_address].message_state)
        else:
            self._blockchain.close_channel_default_split(channel_address)

    def appeal_closed_chan(self, channel_address):
        """
        Checks if the channel at the given address needs to be appealed. If so, an appeal is sent to the
        blockchain.
        :param contract_address: channel address
        :return:
        """
        self._blockchain.appeal_closed_channel(self._channels[channel_address].message_state)

    def withdraw_funds(self, channel_address):
        """
        Allows the user to withdraw funds from the contract into his address.
        :param contract_address: channel address
        """
        fund = self._blockchain.withdraw_fund(channel_address, self._account_address)
        if fund:
            self._balance += fund
            del self._channels[channel_address]

    # TODO: add HTLC
    # TODO: add HTLC
