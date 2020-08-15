import Blockchain
import ChannelManager as cm
from typing import Dict, List, Tuple, Set


class MessageState:
    def __init__(self, owner1_balance, serial, channel_address=None):
        self.owner1_balance = owner1_balance
        self._serial = serial
        self.channel_address = channel_address

    @property
    def serial_number(self):
        return self._serial

# TODO: move MessageState out of here

class Contract_HTLC:
    def __init__(self, owner1_balance_delta, hash_image: int, expiration_block_number: int, attached_channel: cm.ChannelManager):
        self._owner1_balance_delta = owner1_balance_delta
        self._hash_image: int = hash_image
        self._expiration_block_number: int = expiration_block_number
        self._channel_to_notify: cm.ChannelManager = attached_channel
        self._pre_image = None

    @property
    def is_expired(self):
        return Blockchain.BLOCKCHAIN_INSTANCE.block_number >= self._expiration_block_number

    @property
    def expiration_block_number(self):
        return self._expiration_block_number

    @property
    def owner1_balance_delta(self):
        return self._owner1_balance_delta

    @property
    def hash_image(self):
        return self._hash_image

    @property
    def attached_channel(self):
        return self._channel_to_notify

    @property
    def is_valid(self):
        return self._pre_image is not None

    @property
    def pre_image(self):
        return self._pre_image

    def resolve_onchain(self, pre_image: str) -> bool:
        if not self._validate(pre_image):
            return False

        Blockchain.BLOCKCHAIN_INSTANCE.resolve_htlc_contract(self)

        self._channel_to_notify.channel_state.channel_data.owner1.notify_of_resolve_htlc_onchain(self)
        self._channel_to_notify.channel_state.channel_data.owner2.notify_of_resolve_htlc_onchain(self)

        return True

    def _validate(self, pre_image: str) -> bool:
        if self.is_expired:
            return False

        if hash(pre_image) == self._hash_image:
            self._pre_image = pre_image
            return True

        return False

    def resolve_offchain(self, pre_image: str) -> bool:
        if not self._validate(pre_image):
            return False

        self._channel_to_notify.channel_state.channel_data.owner1.notify_of_resolve_htlc_offchain(self)
        self._channel_to_notify.channel_state.channel_data.owner2.notify_of_resolve_htlc_offchain(self)



        return True
