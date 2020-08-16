import LightningChannel as ln
import random
import string
from typing import *
import Contract_HTLC as cn
from singletons import *


class ChannelData:
    def __init__(self, owner1: 'ln.LightningNode', owner2: 'ln.LightningNode'):
        self.address = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self.owner1 = owner1
        self.owner2 = owner2
        self._total_wei = 0

    @property
    def total_wei(self):
        return self._total_wei

 #  TODO: maybe give up on message state completely


class ChannelState:
    def __init__(self, channel_data: ChannelData, message_state: 'cn.MessageState' = None):
        self.channel_data: ChannelData = channel_data
        self.message_state: 'cn.MessageState' = message_state
        self.htlc_contracts: List['cn.Contract_HTLC'] = []


class ChannelManager(object):  # TODO: maybe change name to just channel
    def __init__(self, data: ChannelData, default_split: 'cn.MessageState'):
        self._owner1_htlc_locked: int = 0
        self._owner2_htlc_locked: int = 0
        self._state: ChannelState = ChannelState(data)
        self._state.channel_data._total_wei = default_split.owner1_balance
        default_split.channel_address = data.address  # TODO: not so pretty...
        self.update_message(default_split)
        self._open = True
        self._amount_owner1_can_transfer_to_owner2 = self._state.message_state.owner1_balance
        self._amount_owner2_can_transfer_to_owner1 = (self.channel_state.channel_data.total_wei -
                                                      self._state.message_state.owner1_balance)

        BLOCKCHAIN_INSTANCE.add_channel(self)

    def owner1_htlc_locked_setter(self, owner1_htlc_locked: int, contract: 'cn.Contract_HTLC'):
        self._owner1_htlc_locked = owner1_htlc_locked - contract.additional_delta_for_locked_funds
        self._compute_amount_owner1_can_transfer_to_owner2()
        assert self._owner1_htlc_locked >= 0

    def _compute_amount_owner1_can_transfer_to_owner2(self):
        self._amount_owner1_can_transfer_to_owner2 = self._state.message_state.owner1_balance - self._owner1_htlc_locked

    def owner2_htlc_locked_setter(self, owner2_htlc_locked: int, contract: 'cn.Contract_HTLC'):
        self._owner2_htlc_locked = owner2_htlc_locked + contract.additional_delta_for_locked_funds
        self._compute_amount_owner2_can_transfer_to_owner1()
        assert self._owner2_htlc_locked >= 0

    def _compute_amount_owner2_can_transfer_to_owner1(self):
        self._amount_owner2_can_transfer_to_owner1 = (self.channel_state.channel_data.total_wei -
                                                      self._state.message_state.owner1_balance) - self._owner2_htlc_locked

    @property
    def channel_state(self) -> ChannelState:
        return self._state

    @property
    def is_open(self):
        return self._open

    @property
    def owner1_balance(self):
        return self._state.message_state.owner1_balance

    @property
    def owner2_balance(self):
        return self.channel_state.channel_data.total_wei - self._state.message_state.owner1_balance

    @property
    def amount_owner1_can_transfer_to_owner2(self):
        return self._amount_owner1_can_transfer_to_owner2

    @property
    def amount_owner2_can_transfer_to_owner1(self):
        return self._amount_owner2_can_transfer_to_owner1

    def is_owner1(self, node: 'ln.LightningNode') -> bool:
        return node.address == self.channel_state.channel_data.owner1.address

    def update_message(self, message_state: 'cn.MessageState') -> None:
        self._check_new_message_state(message_state)
        self.channel_state.message_state = message_state
        self._compute_amount_owner1_can_transfer_to_owner2()
        self._compute_amount_owner2_can_transfer_to_owner1()

    def _check_new_message_state(self, message_state: 'cn.MessageState') -> None:
        if message_state.serial_number < 0 or \
                message_state.owner1_balance > self._state.channel_data.total_wei:
            raise ValueError("Invalid message state received.")

        if self._state.message_state is None:
            return

        if self._state.message_state.serial_number >= message_state.serial_number:
            raise ValueError("Tried to update message with an older one.")

    def owner2_add_funds(self, owner2_amount_in_wei: int):
        self._state.channel_data._total_wei += owner2_amount_in_wei  # TODO: see how to get rid of this warning
        BLOCKCHAIN_INSTANCE.apply_transaction(self.channel_state.channel_data.owner2, owner2_amount_in_wei)
        # self.owner2_add_funds.__code__ = (lambda: None).__code__  # so it can not be set again

    def close_channel(self):
        if not self._open:
            return
        BLOCKCHAIN_INSTANCE.close_channel(self._state.message_state)
        self._open = False

    def add_htlc_contract(self, contract: 'cn.Contract_HTLC') -> bool:
        if contract.owner1_balance_delta >= 0 and (self.amount_owner1_can_transfer_to_owner2 - contract.owner1_balance_delta)\
                > self._state.message_state.owner1_balance:
            return False
        if contract.owner1_balance_delta < 0 and (self.amount_owner2_can_transfer_to_owner1 + contract.owner1_balance_delta)\
                > self._state.channel_data.total_wei - self._state.message_state.owner1_balance:
            return False
        if contract.owner1_balance_delta <= 0:
            self.owner1_htlc_locked_setter(self._owner1_htlc_locked - contract.owner1_balance_delta, contract)
        else:
            self.owner2_htlc_locked_setter(self._owner2_htlc_locked + contract.owner1_balance_delta, contract)
        # subscribe to contract
        self._state.htlc_contracts.append(contract)

    def resolve_htlc(self, contract: 'cn.Contract_HTLC'):
        if contract not in self._state.htlc_contracts:
            return

        self._state.htlc_contracts.remove(contract)
        self._unlock_funds_from_contract(contract)
        self._update_message_state_with_contract(contract)

    def _unlock_funds_from_contract(self, contract: 'cn.Contract_HTLC'):
        if contract.owner1_balance_delta <= 0:
            self.owner1_htlc_locked_setter(self._owner1_htlc_locked + contract.owner1_balance_delta, contract)
        else:
            self.owner2_htlc_locked_setter(self._owner2_htlc_locked - contract.owner1_balance_delta, contract)

    def _update_message_state_with_contract(self, contract: 'cn.Contract_HTLC'):
        current_message_state = self._state.message_state
        message_state = cn.MessageState(current_message_state.owner1_balance + contract.owner1_balance_delta,
                                        current_message_state.serial_number + 1,
                                        self._state.channel_data.address)
        self.update_message(message_state)
