import time
from typing import Dict, List, Tuple, Set
import random
import string

BLOCK_IN_DAY = 5

APPEAL_PERIOD = 3  # the appeal period in blocks.
STARTING_SERIAL = 0  # first serial number


class BlockChain:
    def __init__(self):
        self._block_number = 0
        self._open_channels: Dict[str, ChannelData] = {}
        self._closed_channels: Dict[str, ClosedChannelData] = {}

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
        self._closed_channels[message_state.channel_address] = ClosedChannelData(channel, message_state.serial,
                                                                                     self._block_number)

    def close_channel_default_split(self, channel_address):
        if channel_address in self._open_channels:
            channel = self._open_channels[channel_address]
            del self._open_channels[channel_address]
            self._closed_channels[channel_address] = ClosedChannelData(channel, -1, self._block_number)

    def appeal_closed_channel(self, message_state: 'ChannelMessage'):
        closed_channel = self._closed_channels[message_state.channel_address]
        channel = closed_channel.channel
        if closed_channel.block_number + APPEAL_PERIOD > self._block_number and closed_channel.serial < \
                message_state.serial:
            other_balance = channel.total_wei - message_state.balance
            if message_state.owner_address == channel.owner1:
                channel.owner1_balance = message_state.balance
                channel.owner2_balance = other_balance
            else:
                channel.owner2_balance = message_state.balance
                channel.owner1_balance = other_balance
            self._closed_channels[message_state.channel_address] = ClosedChannelData(channel, message_state.serial,
                                                                                     self._block_number)

    def withdraw_fund(self, channel_address, account_address):
        # TODO: remove from dict?
        if self._closed_channels[channel_address] and self._closed_channels[channel_address].block_number + \
                APPEAL_PERIOD <= self._block_number:
            channel = self._closed_channels[channel_address].channel
            fund = channel.owner1_balance
            if channel.owner1 == account_address:
                channel.owner1_balance = 0
            else:
                fund = channel.owner2_balance
                channel.owner2_balance = 0
            return fund

    def appeal_closed_channel_htlc(self, message_state: 'ChannelMessageHTLC', secret_x):
        channel_address = message_state.channel_address
        closed_channel = self._closed_channels[channel_address]
        if message_state.h_of_x == hash(secret_x) and message_state.time_in_days * BLOCK_IN_DAY + \
                message_state.block_number > self._block_number and closed_channel.block_number + \
                APPEAL_PERIOD > self._block_number and closed_channel.serial < message_state.serial:
            self.appeal_closed_channel(message_state)
            self._closed_channels[channel_address] = ClosedChannelHtlcData(self._closed_channels[channel_address], secret_x)

    def close_channel_htlc(self, message_state: 'ChannelMessageHTLC', secret_x):
        channel_address = message_state.channel_address
        if message_state.h_of_x == hash(secret_x) and message_state.time_in_days * BLOCK_IN_DAY + \
                message_state.block_number > self._block_number:
            self.close_channel(message_state)
            self._closed_channels[channel_address] = ClosedChannelHtlcData(self._closed_channels[channel_address], secret_x)

    def get_closed_channel_secret_x(self, channel_address):
        if channel_address in self._closed_channels:
            # TODO: change?
            return self._closed_channels[channel_address].secret_x


class ChannelData:
    def __init__(self, owner1=None, owner2=None, total_wei=None):
        self.address = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self.owner1 = owner1
        self.owner2 = owner2
        self.owner1_balance = total_wei
        self.owner2_balance = 0
        self.total_wei = total_wei


class ClosedChannelData:
    def __init__(self, channel: ChannelData, serial, block_number):
        self.channel = channel
        self.serial = serial
        self.block_number = block_number


class ClosedChannelHtlcData(ClosedChannelData):
    def __init__(self, closed_channel: ClosedChannelData, secret_x):
        super().__init__(closed_channel.channel, closed_channel.serial, closed_channel.block_number)
        self.secret_x = secret_x


class ChannelMessage:
    def __init__(self, owner_address, balance, serial, channel_address):
        self.owner_address = owner_address
        self.serial = serial
        # self.sig = sig
        # Assume balance is the amount of wei for the Node holding this message state
        self.balance = balance
        self.channel_address = channel_address


class ChannelMessageHTLC(ChannelMessage):
    def __init__(self, owner_address, balance, serial, channel_address, h_of_x, block_number, time_in_days):
        super().__init__(owner_address, balance, serial, channel_address)
        self.h_of_x = h_of_x
        self.block_number = block_number
        self.time_in_days = time_in_days


class ChannelState:
    def __init__(self, channel_data: ChannelData, message_state: ChannelMessage = None,
                 message_state_htlc: ChannelMessageHTLC = None):
        self.channel_data: ChannelData = channel_data
        self.message_state: ChannelMessage = message_state
        # TODO: change to list
        self.message_htlc: ChannelMessageHTLC = message_state_htlc


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
        self._other_nodes_to_channels: Dict[str, ChannelState] = {}
        self._hash_to_secret_key: Dict[str, str] = {}
        self._channels: Dict[str, ChannelState] = {}
        self._blockchain = blockchain
        self._balance = 10

    def get_address(self):
        """
        Returns the address of this node on the blockchain (its ethereum wallet).
        """
        return self._account_address

    def get_balance(self):
        """
        Returns the address of this node on the blockchain (its ethereum wallet).
        """
        return self._balance

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
        other_new_balance, serial = self._get_other_new_balance_and_serial(channel_state, amount_in_wei)

        new_message_state = ChannelMessage(other_node.get_address(), other_new_balance, serial, channel_address)
        returned_message_state = other_node.receive(new_message_state, self._account_address)
        channel_state.message_state = returned_message_state

    def start_htlc(self, amount_in_wei, final_node: 'LightningNode', nodes_between: List['LightningNode']):
        """
        Sends money to the other address in the channel, and notifies the other node (calling its recieve()).
        :param contract_address: the channel address
        :param amount_in_wei: the amount to send to the other account
        :param other_node: the other account node
        """
        h_of_x = final_node.generate_secret_x()
        node_to_send = nodes_between[0] if nodes_between else final_node
        self.send_htlc(node_to_send, amount_in_wei, h_of_x, nodes_between)

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
        self._hash_to_secret_key[hash(x)] = x
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

    def close_channel_htlc(self, channel_address):
        """
        Closes the channel at the given contract address.
        :param contract_address: channel address
        :param channel_state: this is the latest state which is signed by the other node, or None,
        if the channel is to be closed using its current balance allocation.
        """
        if self._channels[channel_address].message_htlc:
            message_htlc = self._channels[channel_address].message_htlc
            self._blockchain.close_channel_htlc(message_htlc, self._hash_to_secret_key[message_htlc.h_of_x])

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

    def find_secret_x(self, channel_closed):
        secret_x = self._blockchain.get_closed_channel_secret_x(channel_closed)
        self._hash_to_secret_key[hash(secret_x)] = secret_x

