import channel_manager as cm
import lightning_node as ln
from singletons import *


class Contract_HTLC:
    def __init__(self, amount_in_wei: int, hash_x: int, hash_r: int, expiration_block_number: int,
                 attached_channel: cm.Channel, payer: 'ln.LightningNode', payee: 'ln.LightningNode'):
        # TODO: remove what does not belong to regular htlc
        assert amount_in_wei > 0

        self._amount_in_wei: int = amount_in_wei
        self._hash_x: int = hash_x
        self._hash_r: int = hash_r
        self._expiration_block_number: int = expiration_block_number
        self._channel_to_notify: cm.Channel = attached_channel
        self._pre_image_x = None
        self._pre_image_r = None
        self._payer = payer
        self._payee = payee  # TODO: change to payer and payee
        self._is_valid = True

        self._money_to_transfer_to_payee = 0

        FUNCTION_COLLECTOR_INSTANCE.append(self._on_expired, expiration_block_number)
        FUNCTION_COLLECTOR_INSTANCE.append(self._check_is_pre_image_available, expiration_block_number - 1)

    def _on_expired(self):
        assert self.is_expired

    def _check_is_pre_image_available(self):
        x = BLOCKCHAIN_INSTANCE.get_pre_image_if_exists_onchain(self.hash_x)
        if x:
            self.report_x(x)
            return
        r = BLOCKCHAIN_INSTANCE.get_pre_image_if_exists_onchain(self.hash_r)
        if r:
            self.report_r(r)

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
        return self._payer

    @property
    def receiver(self):
        return self._payee

    @property
    def transfer_amount_to_payee(self):
        return self._money_to_transfer_to_payee

    def invalidate(self):
        self._is_valid = False

    # def accept(self, sender: 'ln.LightningNode'):
    #     if sender == self._sender:
    #         self._is_accepted = True TODO: do we need this now?

    def report_x(self, x: str):
        assert not self.is_expired
        assert self._pre_image_x is None and self._pre_image_r is None
        assert hash(x) == self.hash_x
        self._pre_image_x = x

    def report_r(self, r: str):
        assert not self.is_expired
        assert self._pre_image_x is None and self._pre_image_r is None
        assert hash(r) == self.hash_r
        self._pre_image_r = r


class ContractForward(Contract_HTLC):
    def __init__(self, amount_in_wei: int, hash_x: int, hash_r: int, expiration_block_number: int,
                 attached_channel: cm.Channel, payer: 'ln.LightningNode', payee: 'ln.LightningNode'):
        super().__init__(amount_in_wei, hash_x, hash_r, expiration_block_number, attached_channel, payer, payee)

        # when expired or revealed r - money goes to owner 1. if revealed x - to owner 2 TODO: communicate with channel and not
        #  owner

    def _on_expired(self):
        if self._pre_image_r or self._pre_image_x or not self._channel_to_notify.is_open or not \
                self._is_valid:
            return
        super()._on_expired()

        self._channel_to_notify.notify_of_end_of_contract(self)

    def report_x(self, x: str):
        super().report_x(x)
        self._money_to_transfer_to_receiver = self.amount_in_wei
        self.attached_channel.notify_of_end_of_contract(self)

    def report_r(self, r: str):
        super().report_r(r)
        self.attached_channel.notify_of_end_of_contract(self)

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
                 attached_channel: cm.Channel, payer: 'ln.LightningNode', payee: 'ln.LightningNode'):
        super().__init__(amount_in_wei, hash_x, hash_r, expiration_block_number, attached_channel, payer, payee)

        # when expired - money goes to owner 2. if revealed - to owner 1 TODO: communicate with channel and not owner

        # TODO: maybe hold the other contract in the path?

    def _on_expired(self):
        if self._pre_image_r or self._pre_image_x or not self._channel_to_notify.is_open or not \
                self._is_valid:
            return
        super()._on_expired()

        self._money_to_transfer_to_receiver = self.amount_in_wei
        self._channel_to_notify.notify_of_end_of_contract(self)

    def report_x(self, x: str):
        super().report_x(x)
        self.attached_channel.notify_of_end_of_contract(self)

    def report_r(self, r: str):
        super().report_r(r)
        self.attached_channel.notify_of_end_of_contract(self)
