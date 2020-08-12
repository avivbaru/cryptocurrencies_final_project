from LightningChannel import *
from Contract_HTLC import MessageState
from Blockchain import *
import random
import string
import Contract_HTLC


class ChannelData:
    def __init__(self, owner1=None, owner2=None):
        self.address = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self.owner1 = owner1
        self.owner2 = owner2
        self._total_wei = 0

    @property
    def total_wei(self):
        return self._total_wei


class ChannelState:
    def __init__(self, channel_data: ChannelData, message_state: MessageState = None):
        self.channel_data: ChannelData = channel_data
        self.message_state: MessageState = message_state


class ChannelManager(object):  # TODO: maybe change name to just channel
    def __init__(self, data: ChannelData, default_split: MessageState):
        self._state: ChannelState = ChannelState(data)
        self._state.channel_data._total_wei = default_split.owner1_balance
        default_split.channel_address = data.address  # TODO: not so pretty...
        self.update_message(default_split)
        self._htlc_contracts: List[Contract_HTLC] = []
        self._open = True

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
        # TODO: consider locked funds in htlc here
        return self._state.message_state.owner1_balance

    @property
    def amount_owner2_can_transfer_to_owner1(self):
        # TODO: consider locked funds in htlc here
        return self.channel_state.channel_data.total_wei - self._state.message_state.owner1_balance

    def update_message(self, message_state: MessageState) -> None:
        self._check_new_message_state(message_state)
        self.channel_state.message_state = message_state

    def _check_new_message_state(self, message_state: MessageState) -> None:
        if message_state.serial_number < 0 or \
                message_state.owner1_balance > self._state.channel_data.total_wei or not message_state.is_valid:
            raise ValueError("Invalid message state received.")

        if self._state.message_state is None:
            return

        if self._state.message_state.serial_number >= message_state.serial_number:
            raise ValueError("Tried to update message with an older one.")

    def owner2_add_funds(self, owner2_amount_in_wei: int):
        self._state.channel_data._total_wei += owner2_amount_in_wei  # TODO: see how to get rid of this warning
        self.owner2_add_funds.__code__ = (lambda: None).__code__  # so it can not be set again

    def close_channel(self):
        BLOCKCHAIN_INSTANCE.close_channel(self._state.message_state)
        self._open = False

    def add_htlc_contract(self, contract: Contract_HTLC):
        self._htlc_contracts.append(contract)


