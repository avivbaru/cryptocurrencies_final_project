import channel_manager as cm
import lightning_node as ln
from singletons import *


class Contract_HTLC:
    def __init__(self, transaction_id: int, amount_in_wei: int, hash_x: int, hash_r: int, expiration_block_number: int,
                 attached_channel: cm.Channel, payer: 'ln.LightningNode', payee: 'ln.LightningNode'):
        assert amount_in_wei > 0

        self._transaction_id = transaction_id  # for debugging purposes
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

    def _on_expired(self):
        assert self.is_expired

    @property
    def is_expired(self):
        return BLOCKCHAIN_INSTANCE.block_number >= self._expiration_block_number

    @property
    def expiration_block_number(self):
        return self._expiration_block_number

    @property
    def transaction_id(self) -> int:
        return self._transaction_id

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
    def payer(self):
        return self._payer

    @property
    def payee(self):
        return self._payee

    @property
    def transfer_amount_to_payee(self):
        return self._money_to_transfer_to_payee


    @property
    def is_concluded(self):
        return not self._is_valid or self.is_expired or self._pre_image_x or self._pre_image_r

    def invalidate(self):
        self._is_valid = False
        self._payee.notify_of_contract_invalidation(self)
        self._payer.notify_of_contract_invalidation(self)

    def report_x(self, x: str):
        assert not self.is_expired
        assert self._is_valid
        assert self._pre_image_x is None and self._pre_image_r is None
        assert hash(x) == self.hash_x
        self._pre_image_x = x

    def report_r(self, r: str):
        assert not self.is_expired
        assert self._is_valid
        assert self._pre_image_x is None and self._pre_image_r is None
        assert hash(r) == self.hash_r
        self._pre_image_r = r


class ContractForward(Contract_HTLC):
    def __init__(self, transaction_id: int, amount_in_wei: int, hash_x: int, hash_r: int, expiration_block_number: int,
                 attached_channel: cm.Channel, payer: 'ln.LightningNode', payee: 'ln.LightningNode'):
        super().__init__(transaction_id, amount_in_wei, hash_x, hash_r, expiration_block_number, attached_channel, payer, payee)

    def _on_expired(self):
        if self._pre_image_r or self._pre_image_x or not self._channel_to_notify.is_open or not self._is_valid:
            return
        super()._on_expired()

        self._channel_to_notify.notify_of_end_of_contract(self)

    def report_x(self, x: str):
        super().report_x(x)
        self._money_to_transfer_to_payee = self.amount_in_wei
        self.attached_channel.notify_of_end_of_contract(self)

    def report_r(self, r: str):
        super().report_r(r)
        self.attached_channel.notify_of_end_of_contract(self)


class ContractCancellation(Contract_HTLC):
    def __init__(self, transaction_id: int, amount_in_wei: int, hash_x: int, hash_r: int, expiration_block_number: int,
                 attached_channel: cm.Channel, payer: 'ln.LightningNode', payee: 'ln.LightningNode'):
        super().__init__(transaction_id, amount_in_wei, hash_x, hash_r, expiration_block_number, attached_channel, payer, payee)

    def _on_expired(self):
        if self._pre_image_r or self._pre_image_x or not self._channel_to_notify.is_open or not self._is_valid:
            return
        super()._on_expired()

        self._money_to_transfer_to_payee = self.amount_in_wei
        self._channel_to_notify.notify_of_end_of_contract(self)
        self.payee.notify_of_cancellation_contract_payment(self)

    def report_x(self, x: str):
        super().report_x(x)
        self.attached_channel.notify_of_end_of_contract(self)

    def report_r(self, r: str):
        super().report_r(r)
        self.attached_channel.notify_of_end_of_contract(self)
