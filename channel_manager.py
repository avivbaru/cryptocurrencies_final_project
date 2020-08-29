import lightning_node as ln
import random
import string
from typing import *
import contract_htlc as cn
from singletons import *


class MessageState:
    def __init__(self, owner1_balance, serial, channel_address=None):
        self.owner1_balance = owner1_balance
        self._serial = serial
        self.channel_address = channel_address

    @property
    def serial_number(self):
        return self._serial


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
    def __init__(self, channel_data: ChannelData, message_state: 'MessageState' = None):
        self.channel_data: ChannelData = channel_data
        self.message_state: 'cn.MessageState' = message_state
        self.htlc_contracts: List['cn.Contract_HTLC'] = []


class Channel(object):  # TODO: maybe change name to just channel
    def __init__(self, data: ChannelData, default_split: 'MessageState'):
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

    def owner1_htlc_locked_setter(self, owner1_htlc_locked: int):
        assert owner1_htlc_locked >= 0
        old_htlc_locked = self._owner1_htlc_locked
        self._owner1_htlc_locked = owner1_htlc_locked
        self._compute_amount_owner1_can_transfer_to_owner2()
        self._state.channel_data.owner1.notify_of_change_in_locked_funds(self._owner1_htlc_locked - old_htlc_locked)

    def _compute_amount_owner1_can_transfer_to_owner2(self):
        self._amount_owner1_can_transfer_to_owner2 = self._state.message_state.owner1_balance - self._owner1_htlc_locked
        assert self._amount_owner1_can_transfer_to_owner2 >= 0

    def owner2_htlc_locked_setter(self, owner2_htlc_locked: int):
        assert owner2_htlc_locked >= 0
        old_htlc_locked = self._owner2_htlc_locked
        self._owner2_htlc_locked = owner2_htlc_locked
        self._compute_amount_owner2_can_transfer_to_owner1()
        self._state.channel_data.owner2.notify_of_change_in_locked_funds(self._owner2_htlc_locked - old_htlc_locked)

    def _compute_amount_owner2_can_transfer_to_owner1(self):
        self._amount_owner2_can_transfer_to_owner1 = (self.channel_state.channel_data.total_wei -
                                                      self._state.message_state.owner1_balance) - self._owner2_htlc_locked
        assert self._amount_owner2_can_transfer_to_owner1 >= 0

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

    def update_message(self, message_state: 'MessageState') -> None:
        self._check_new_message_state(message_state)
        self.channel_state.message_state = message_state
        self._compute_amount_owner1_can_transfer_to_owner2()
        self._compute_amount_owner2_can_transfer_to_owner1()

    def _check_new_message_state(self, message_state: 'MessageState') -> None:
        if message_state.serial_number < 0 or message_state.owner1_balance > self._state.channel_data.total_wei:
            raise ValueError("Invalid message state received.")

        if self._state.message_state is None:
            return

        if self._state.message_state.serial_number >= message_state.serial_number:
            raise ValueError("Tried to update message with an older one.")

    def owner2_add_funds(self, owner2_amount_in_wei: int):
        self._state.channel_data._total_wei += owner2_amount_in_wei  # TODO: see how to get rid of this warning
        self._compute_amount_owner2_can_transfer_to_owner1()
        BLOCKCHAIN_INSTANCE.apply_transaction(self.channel_state.channel_data.owner2, owner2_amount_in_wei)
        # self.owner2_add_funds.__code__ = (lambda: None).__code__  # so it can not be set again

    def close_channel(self):
        if not self._open:
            return
        BLOCKCHAIN_INSTANCE.close_channel(self._state.message_state)
        self.owner1_htlc_locked_setter(0)
        self.owner2_htlc_locked_setter(0)
        self._state.channel_data.owner1.notify_of_closed_channel(self, self._state.channel_data.owner2)
        self._state.channel_data.owner2.notify_of_closed_channel(self, self._state.channel_data.owner1)
        self._open = False

    def add_contract(self, contract: 'cn.Contract_HTLC') -> bool:
        if self.is_owner1(contract.sender):
            if self.amount_owner1_can_transfer_to_owner2 < contract.amount_in_wei:
                return False  # TODO: report failure
            self.owner1_htlc_locked_setter(self._owner1_htlc_locked + contract.amount_in_wei)
        else:
            if self.amount_owner2_can_transfer_to_owner1 < contract.amount_in_wei:
                return False
            self.owner2_htlc_locked_setter(self._owner2_htlc_locked + contract.amount_in_wei)
        # TODO: subscribe to contract?
        self._state.htlc_contracts.append(contract)
        return True

    # def resolve_htlc(self, contract: 'cn.Contract_HTLC'):
    #     if contract not in self._state.htlc_contracts:
    #         return
    #
    #     self._state.htlc_contracts.remove(contract)
    #     self._unlock_funds_from_contract(contract)
    #     self._update_message_state_with_contract(contract)

    # def _unlock_funds_from_contract(self, contract: 'cn.Contract_HTLC'):
    #     if contract.owner1_balance_delta <= 0:
    #         self.owner1_htlc_locked_setter(self._owner1_htlc_locked + contract.owner1_balance_delta)
    #     else:
    #         self.owner2_htlc_locked_setter(self._owner2_htlc_locked - contract.owner1_balance_delta)

    def _update_message_state(self, new_owner1_balance: int):
        current_message_state = self._state.message_state
        message_state = MessageState(new_owner1_balance, current_message_state.serial_number + 1,
                                        self._state.channel_data.address)
        self.update_message(message_state)

    def notify_of_end_of_contract(self, contract: 'cn.Contract_HTLC'):
        # assert contract in self._state.htlc_contracts TODO: this fails cause contract is not added but gets expired - fix it
        #  by adding a "invalidate" option to contracts - the if is a fix for now
        self._handle_contract_ended(contract)

        if contract.is_expired:
            for other_contract in self._state.htlc_contracts:
                self._handle_contract_ended(other_contract)
            self._state.htlc_contracts = []
            self.close_channel()  # resolve on-chain

    def _handle_contract_ended(self, contract: 'cn.Contract_HTLC'):
        self._state.htlc_contracts.remove(contract)

        locked_for_owner1 = 0
        locked_for_owner2 = 0
        transfer_to_owner1 = 0
        transfer_to_owner2 = 0
        if self.is_owner1(contract.sender):
            locked_for_owner1 = contract.amount_in_wei
            transfer_to_owner2 = contract.transfer_amount_to_payee
        else:
            locked_for_owner2 = contract.amount_in_wei
            transfer_to_owner1 = contract.transfer_amount_to_payee

        self.owner1_htlc_locked_setter(int(self._owner1_htlc_locked - locked_for_owner1))
        self.owner2_htlc_locked_setter(int(self._owner2_htlc_locked - locked_for_owner2))

        new_owner1_balance = self._state.message_state.owner1_balance + transfer_to_owner1 - transfer_to_owner2
        self._update_message_state(new_owner1_balance)

        if contract.pre_image_x:
            BLOCKCHAIN_INSTANCE.report_pre_image(contract.hash_x, contract.pre_image_x)
        elif contract.pre_image_r:
            BLOCKCHAIN_INSTANCE.report_pre_image(contract.hash_r, contract.pre_image_r)
