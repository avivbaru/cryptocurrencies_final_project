import channel_manager as cm
import lightning_node as ln
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
    def __init__(self, amount_in_wei: int, hash_x: int, hash_r: int, expiration_block_number: int,
                 attached_channel: cm.ChannelManager, sender: 'ln.LightningNode', receiver: 'ln.LightningNode'):
        assert amount_in_wei > 0

        self._amount_in_wei: int = amount_in_wei
        self._hash_x: int = hash_x
        self._hash_r: int = hash_r
        self._expiration_block_number: int = expiration_block_number
        self._channel_to_notify: cm.ChannelManager = attached_channel
        self._pre_image_x = None
        self._pre_image_r = None
        self._sender = sender
        self._receiver = receiver
        self._is_accepted = False
        self._money_to_transfer_to_sender = 0
        self._money_to_transfer_to_receiver = 0

        FUNCTION_COLLECTOR_INSTANCE.append(self._on_expired, expiration_block_number)

    def _on_expired(self):
        assert self.is_expired
        self._channel_to_notify.notify_of_end_of_contract(self)

    @property
    def is_expired(self):
        return BLOCKCHAIN_INSTANCE.block_number >= self._expiration_block_number

    @property
    def expiration_block_number(self):
        return self._expiration_block_number

    @property
    def amount_in_wei(self) -> int:
        return self._amount_in_wei

    @property
    def hash_x(self):
        return self._hash_x

    @property
    def hash_r(self):
        return self._hash_r

    @property
    def attached_channel(self):
        return self._channel_to_notify

    @property
    def pre_image_x(self):
        return self._pre_image_x

    @property
    def pre_image_r(self):
        return self._pre_image_r

    @property
    def sender(self):
        return self._sender

    @property
    def receiver(self):
        return self._receiver

    @property
    def transfer_amount_to_sender(self):
        return self._money_to_transfer_to_sender

    @property
    def transfer_amount_to_receiver(self):
        return self._money_to_transfer_to_receiver

    @property
    def is_accepted(self):
        return self._is_accepted

    # def accept(self, sender: 'ln.LightningNode'):
    #     if sender == self._sender:
    #         self._is_accepted = True TODO: do we need this now?

    def report_x(self, x: int):
        assert not self.is_expired
        assert self._pre_image_x is None and self._pre_image_r is None
        assert hash(x) == self.hash_x
        self._pre_image_x = x

    def report_r(self, r: int):
        assert not self.is_expired
        assert self._pre_image_x is None and self._pre_image_r is None
        assert hash(r) == self.hash_r
        self._pre_image_r = r


class ContractForward(Contract_HTLC):
    def __init__(self, amount_in_wei: int, hash_x: int, hash_r: int, expiration_block_number: int,
                 attached_channel: cm.ChannelManager, sender: 'ln.LightningNode', receiver: 'ln.LightningNode'):
        super().__init__(amount_in_wei, hash_x, hash_r, expiration_block_number, attached_channel, sender, receiver)

        # when expired or revealed r - money goes to owner 1. if revealed x - to owner 2 TODO: communicate with channel and not
        #  owner

    def _on_expired(self):
        super()._on_expired()
        self._money_to_transfer_to_owner1 = self.amount_in_wei
        self._money_to_transfer_to_owner2 = 0

    def report_x(self, x: int):
        super().report_x(x)
        self.attached_channel.notify_of_end_of_contract(self)
        self._money_to_transfer_to_owner1 = 0
        self._money_to_transfer_to_owner2 = self.amount_in_wei

    def report_r(self, r: int):
        super().report_r(r)
        self.attached_channel.notify_of_end_of_contract(self)
        self._money_to_transfer_to_owner1 = self.amount_in_wei
        self._money_to_transfer_to_owner2 = 0

    # def resolve_onchain(self, pre_image: str) -> bool:
    #     if not self._validate(pre_image):
    #         return False
    #
    #     self._resolve_onchain()
    #     return True
    #
    # def _resolve_onchain(self):
    #     # BLOCKCHAIN_INSTANCE.resolve_htlc_contract(self)
    #
    #     self._channel_to_notify.channel_state.channel_data.owner1.notify_of_resolve_htlc_onchain(self)
    #     self._channel_to_notify.channel_state.channel_data.owner2.notify_of_resolve_htlc_onchain(self)

    # def _validate(self, pre_image: str) -> bool:
    #     if self.is_expired:
    #         return False
    #
    #     if hash(pre_image) == self._hash_image:
    #         self._pre_image = pre_image
    #         return True
    #
    #     return False
    #
    # def resolve_offchain(self, pre_image: str) -> bool:
    #     if not self._validate(pre_image):
    #         return False
    #
    #     return True

    # def resolve_griefed_contract(self):
    #     self._resolve_onchain()


class ContractCancellation(Contract_HTLC):
    def __init__(self, amount_in_wei: int, hash_x: int, hash_r: int, expiration_block_number: int,
                 attached_channel: cm.ChannelManager, sender: 'ln.LightningNode', receiver: 'ln.LightningNode'):
        super().__init__(amount_in_wei, hash_x, hash_r, expiration_block_number, attached_channel, sender, receiver)

        # when expired - money goes to owner 2. if revealed - to owner 1 TODO: communicate with channel and not owner

        # TODO: maybe hold the other contract in the path?

    def _on_expired(self):
        super()._on_expired()
        self._money_to_transfer_to_sender = 0
        self._money_to_transfer_to_receiver = self.amount_in_wei

    def report_x(self, x: int):
        super().report_x(x)
        self.attached_channel.notify_of_end_of_contract(self)
        self._money_to_transfer_to_sender = self.amount_in_wei
        self._money_to_transfer_to_receiver = 0

    def report_r(self, r: int):
        super().report_r(r)
        self.attached_channel.notify_of_end_of_contract(self)
        self._money_to_transfer_to_sender = self.amount_in_wei
        self._money_to_transfer_to_receiver = 0
