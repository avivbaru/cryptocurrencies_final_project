import channel_manager as cm
import lightning_channel as ln
from singletons import *


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
    def __init__(self, owner1_balance_delta: int, hash_image: int, expiration_block_number: int, attached_channel:
                 cm.ChannelManager, owner1: 'ln.LightningNode', owner2: 'ln.LightningNode'):
        self._owner1_balance_delta: int = int(owner1_balance_delta)
        self._hash_image: int = hash_image
        self._expiration_block_number: int = expiration_block_number
        self._channel_to_notify: cm.ChannelManager = attached_channel
        self._pre_image = None
        self._owner1 = owner1
        self._owner2 = owner2

        FUNCTION_COLLECTOR_INSTANCE.append(lambda: self.owner1.notify_of_griefed_contract(self),
                                           self._expiration_block_number)

    @property
    def is_expired(self):
        return BLOCKCHAIN_INSTANCE.block_number >= self._expiration_block_number

    @property
    def expiration_block_number(self):
        return self._expiration_block_number

    @property
    def owner1_balance_delta(self) -> int:
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

    @property
    def owner1(self):
        return self._owner1

    @property
    def owner2(self):
        return self._owner2

    def additional_delta_for_locked_funds(self, owner: 'ln.LightningNode') -> int:
        return 0

    # def check_expiration(self) -> bool:
    #     if self.is_expired:
    #         self.owner1.notify_of_griefed_contract(self)
    #         return True
    #     return False

    def resolve_onchain(self, pre_image: str) -> bool:
        if not self._validate(pre_image):
            return False

        self._resolve_onchain()
        return True

    def _resolve_onchain(self):
        # BLOCKCHAIN_INSTANCE.resolve_htlc_contract(self)

        self._channel_to_notify.channel_state.channel_data.owner1.notify_of_resolve_htlc_onchain(self)
        self._channel_to_notify.channel_state.channel_data.owner2.notify_of_resolve_htlc_onchain(self)

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

        return True

    def resolve_griefed_contract(self):
        self._resolve_onchain()
