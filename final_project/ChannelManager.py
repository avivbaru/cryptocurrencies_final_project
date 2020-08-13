import LightningChannel as ln
from Blockchain import *
import random
import string
import Contract_HTLC as cn


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
        self.message_state: 'MessageState' = message_state
        self.htlc_contracts: List['Contract_HTLC'] = []


class ChannelManager(object):  # TODO: maybe change name to just channel
    def __init__(self, data: ChannelData, default_split: 'MessageState'):
        self._state: ChannelState = ChannelState(data)
        self._state.channel_data._total_wei = default_split.owner1_balance
        default_split.channel_address = data.address  # TODO: not so pretty...
        self.update_message(default_split)
        self._open = True
        self._owner1_htlc_locked = 0
        self._owner2_htlc_locked = 0

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
        return self._state.message_state.owner1_balance - self._owner1_htlc_locked

    @property
    def amount_owner2_can_transfer_to_owner1(self):
        return (self.channel_state.channel_data.total_wei - self._state.message_state.owner1_balance) - self._owner2_htlc_locked

    def update_message(self, message_state: 'MessageState') -> None:
        self._check_new_message_state(message_state)
        self.channel_state.message_state = message_state

    def _check_new_message_state(self, message_state: 'MessageState') -> None:
        if message_state.serial_number < 0 or \
                message_state.owner1_balance > self._state.channel_data.total_wei:
            raise ValueError("Invalid message state received.")

        if self._state.message_state is None:
            return

        if self._state.message_state.serial_number >= message_state.serial_number:
            raise ValueError("Tried to update message with an older one.")

    def owner2_add_funds(self, owner2_amount_in_wei: int):
        self._state.channel_data._total_wei += owner2_amount_in_wei  # TODO: see how to get rid of this warning
        # self.owner2_add_funds.__code__ = (lambda: None).__code__  # so it can not be set again

    def close_channel(self):
        BLOCKCHAIN_INSTANCE.close_channel(self._state.message_state)
        self._open = False

    def add_htlc_contract(self, contract: 'Contract_HTLC') -> bool:
        if contract.owner1_balance_delta >= 0 and (self.amount_owner1_can_transfer_to_owner2 - contract.owner1_balance_delta)\
                > self._state.message_state.owner1_balance:
            return False
        if contract.owner1_balance_delta < 0 and (self.amount_owner2_can_transfer_to_owner1 + contract.owner1_balance_delta)\
                > self._state.channel_data.total_wei - self._state.message_state.owner1_balance:
            return False
        if contract.owner1_balance_delta <= 0:
            self._owner1_htlc_locked -= contract.owner1_balance_delta
        else:
            self._owner2_htlc_locked += contract.owner1_balance_delta
        # subscribe to contract
        self._state.htlc_contracts.append(contract)

    def resolve_htlc(self, contract: 'Contract_HTLC'):
        if contract not in self._state.htlc_contracts or not contract.is_valid:
            return

        self._state.htlc_contracts.remove(contract)
        self._unlock_funds_from_contract(contract)

    def _unlock_funds_from_contract(self, contract: 'Contract_HTLC'):
        if contract.owner1_balance_delta <= 0:
            self._owner1_htlc_locked += contract.owner1_balance_delta
        else:
            self._owner2_htlc_locked -= contract.owner1_balance_delta

        current_message_state = self._state.message_state
        message_state = cn.MessageState(current_message_state.owner1_balance + contract.owner1_balance_delta,
                                        current_message_state.serial_number + 1,
                                        self._state.channel_data.address)
        self.update_message(message_state)
