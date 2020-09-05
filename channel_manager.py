import lightning_node as ln
import random
import string
from typing import Optional, List
import contract_htlc as cn
from singletons import *


class MessageState:
    """
    Class to represent a message state of a channel holding the current balance of the channel.
    """
    def __init__(self, owner1_balance, serial, channel_address=None):
        """
        Initializes a new `MessageState`.
        @param owner1_balance: owner1 current balance.
        @param serial: the serial number of this message - used to verify that new states are valid.
        @param channel_address: the address of the corresponding channel.
        """
        self.owner1_balance = owner1_balance
        self._serial = serial
        self.channel_address = channel_address

    @property
    def serial_number(self):
        return self._serial


class ChannelData:
    """
    Class to holds the data of the channel.
    """
    def __init__(self, owner1: 'ln.LightningNode', owner2: 'ln.LightningNode'):
        """
        Initializes a new `ChannelData`.
        @param owner1: First owner of the channel.
        @param owner2: Second owner of the channel.
        """
        self.address = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self.owner1 = owner1
        self.owner2 = owner2
        self.total_wei = 0  # will be changed as owners deposit funds.


class ChannelState:
    """
    Class to represent the state of a specific channel.
    """
    def __init__(self, channel_data: ChannelData, message_state: 'MessageState' = None):
        """
        Initializes a new `ChannelState`.
        @param channel_data: the data of the channel.
        @param message_state: the latest message state of the channel.
        """
        self.channel_data: ChannelData = channel_data
        self.message_state: 'MessageState' = message_state
        self.htlc_contracts: List['cn.Contract_HTLC'] = []  # holds all the htlc contracts of the channel.


class Channel:
    """
    Class to represent a channel between two nodes in the network.
    """
    def __init__(self, data: ChannelData, default_split: 'MessageState'):
        """
        Initializes a new `Channel`.
        @param data: the data of the channel.
        @param default_split: the first split in the channel.
        """
        self._owner1_htlc_locked: int = 0
        self._owner2_htlc_locked: int = 0
        self._state: ChannelState = ChannelState(data)
        self._state.channel_data.total_wei = default_split.owner1_balance
        default_split.channel_address = data.address
        self.update_message(default_split)
        self._open = True
        self._amount_owner1_can_transfer_to_owner2 = self._state.message_state.owner1_balance
        self._amount_owner2_can_transfer_to_owner1 = (self.channel_state.channel_data.total_wei -
                                                      self._state.message_state.owner1_balance)

        BLOCKCHAIN_INSTANCE.add_channel(self)

    @property
    def channel_state(self) -> ChannelState:
        return self._state

    @property
    def is_open(self):
        """
        @return: True iff the channel is open.
        """
        return self._open

    @property
    def owner1_balance(self):
        """
        @return: the amount owner1 will get if the channel will be closed now.
        """
        return self._state.message_state.owner1_balance

    @property
    def owner2_balance(self):
        """
        @return: the amount owner2 will get if the channel will be closed now.
        """
        return self.channel_state.channel_data.total_wei - self._state.message_state.owner1_balance

    @property
    def amount_owner1_can_transfer_to_owner2(self):
        """
        @return: the amount owner1 can currently transfer to owner2 thorough this channel.
        """
        return self._amount_owner1_can_transfer_to_owner2

    @property
    def amount_owner2_can_transfer_to_owner1(self):
        """
        @return: the amount owner2 can currently transfer to owner1 thorough this channel.
        """
        return self._amount_owner2_can_transfer_to_owner1

    def _owner1_htlc_locked_setter(self, owner1_htlc_locked: int):
        assert owner1_htlc_locked >= 0
        old_htlc_locked = self._owner1_htlc_locked
        self._owner1_htlc_locked = owner1_htlc_locked
        self._compute_amount_owner1_can_transfer_to_owner2()
        self._state.channel_data.owner1.notify_of_change_in_locked_funds(self._owner1_htlc_locked - old_htlc_locked)

    def _compute_amount_owner1_can_transfer_to_owner2(self):
        self._amount_owner1_can_transfer_to_owner2 = self._state.message_state.owner1_balance - self._owner1_htlc_locked
        assert self._amount_owner1_can_transfer_to_owner2 >= 0

    def _owner2_htlc_locked_setter(self, owner2_htlc_locked: int):
        assert owner2_htlc_locked >= 0
        old_htlc_locked = self._owner2_htlc_locked
        self._owner2_htlc_locked = owner2_htlc_locked
        self._compute_amount_owner2_can_transfer_to_owner1()
        self._state.channel_data.owner2.notify_of_change_in_locked_funds(self._owner2_htlc_locked - old_htlc_locked)

    def _compute_amount_owner2_can_transfer_to_owner1(self):
        self._amount_owner2_can_transfer_to_owner1 = (self.channel_state.channel_data.total_wei -
                                                      self._state.message_state.owner1_balance) - self._owner2_htlc_locked
        assert self._amount_owner2_can_transfer_to_owner1 >= 0

    def is_owner1(self, node: 'ln.LightningNode') -> bool:
        """
        @return: True if node is owner1 of this channel.
        """
        return node.address == self.channel_state.channel_data.owner1.address

    def update_message(self, message_state: 'MessageState'):
        """
        Updates the current message state with `message_state`.
        """
        self._check_new_message_state(message_state)
        self.channel_state.message_state = message_state
        self._compute_amount_owner1_can_transfer_to_owner2()
        self._compute_amount_owner2_can_transfer_to_owner1()

    def _check_new_message_state(self, message_state: 'MessageState'):
        if message_state.serial_number < 0 or message_state.owner1_balance > self._state.channel_data.total_wei:
            raise ValueError("Invalid message state received.")

        if self._state.message_state is None:
            return

        if self._state.message_state.serial_number >= message_state.serial_number:
            raise ValueError("Tried to update message with an older one.")

    def owner2_add_funds(self, owner2_amount_in_msat: int):
        """
        Adds `owner2_amount_in_msat` to the channel funds, as owner2 balance.
        """
        BLOCKCHAIN_INSTANCE.apply_transaction(self.channel_state.channel_data.owner2, owner2_amount_in_msat)
        self._state.channel_data.total_wei += (owner2_amount_in_msat * (1 - BLOCKCHAIN_INSTANCE.fee))
        self._compute_amount_owner2_can_transfer_to_owner1()

    def close_channel(self):
        """
        Closes this channel with the current message state and notifies the blockchain, owner1 and owner2
        """
        if not self._open:
            return
        for contract in self._state.htlc_contracts:
            contract.invalidate()
        self._state.htlc_contracts = []

        self._owner1_htlc_locked_setter(0)
        self._owner2_htlc_locked_setter(0)

        BLOCKCHAIN_INSTANCE.close_channel(self._state.message_state)

        self._state.channel_data.owner2.notify_of_closed_channel(self, self._state.channel_data.owner1)
        self._state.channel_data.owner1.notify_of_closed_channel(self, self._state.channel_data.owner2)
        self._open = False

    def add_contract(self, contract: 'cn.Contract_HTLC') -> bool:
        """
        Adds a new contract `contract` to the channel.
        @return: True iff the contract was added successfully.
        """
        if self.is_owner1(contract.payer):
            if self.amount_owner1_can_transfer_to_owner2 < contract.amount_in_wei:
                contract.invalidate()
                return False  # TODO: decide where to invalidate
            self._owner1_htlc_locked_setter(self._owner1_htlc_locked + contract.amount_in_wei)
        else:
            if self.amount_owner2_can_transfer_to_owner1 < contract.amount_in_wei:
                contract.invalidate()
                return False
            self._owner2_htlc_locked_setter(self._owner2_htlc_locked + contract.amount_in_wei)
        self._state.htlc_contracts.append(contract)
        return True

    def _update_message_state(self, new_owner1_balance: int):
        current_message_state = self._state.message_state
        message_state = MessageState(new_owner1_balance, current_message_state.serial_number + 1,
                                     self._state.channel_data.address)
        self.update_message(message_state)

    def notify_of_end_of_contract(self, contract: 'cn.Contract_HTLC'):
        """
        Used to notify this channel that the contract `contract` has ended.
        """
        assert contract in self._state.htlc_contracts

        self._state.htlc_contracts.remove(contract)

        locked_for_owner1 = 0
        locked_for_owner2 = 0
        transfer_to_owner1 = 0
        transfer_to_owner2 = 0
        if self.is_owner1(contract.payer):
            locked_for_owner1 = contract.amount_in_wei
            transfer_to_owner2 = contract.transfer_amount_to_payee
        else:
            locked_for_owner2 = contract.amount_in_wei
            transfer_to_owner1 = contract.transfer_amount_to_payee

        self._owner1_htlc_locked_setter(int(self._owner1_htlc_locked - locked_for_owner1))
        self._owner2_htlc_locked_setter(int(self._owner2_htlc_locked - locked_for_owner2))

        new_owner1_balance = self._state.message_state.owner1_balance + transfer_to_owner1 - transfer_to_owner2
        self._update_message_state(new_owner1_balance)

        if contract.pre_image_x:
            BLOCKCHAIN_INSTANCE.report_pre_image(contract.pre_image_x)
        elif contract.pre_image_r:
            BLOCKCHAIN_INSTANCE.report_pre_image(contract.pre_image_r)

    def pay_amount_to_owner(self, owner: 'ln.LightningNode', contract: 'cn.ContractCancellation'):
        """
        Pays the amount in the contract `contract` to the payee `contract.payee`
        """
        assert owner == contract.payee  # TODO: remove this line and owner argument after a few runs
        owner1_new_balance_delta = contract.amount_in_wei
        if self.is_owner1(contract.payee):
            self._owner2_htlc_locked_setter(int(self._owner2_htlc_locked - contract.amount_in_wei))
        else:
            self._owner1_htlc_locked_setter(int(self._owner1_htlc_locked - contract.amount_in_wei))
            owner1_new_balance_delta = -contract.amount_in_wei
        self._update_message_state(self._state.message_state.owner1_balance + owner1_new_balance_delta)
        contract.invalidate()
        self._state.htlc_contracts.remove(contract)
