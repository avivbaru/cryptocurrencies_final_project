import channel_manager as cm
import lightning_node as ln
from singletons import *


class Contract_HTLC:
    """
    An abstract class that represent a contract for transferring money in the lightning network.
    """
    def __init__(self, transaction_id: int, amount_in_msat: int, hash_x: int, hash_r: int, expiration_block_number: int,
                 attached_channel: cm.Channel, payer: 'ln.LightningNode', payee: 'ln.LightningNode'):
        """
        Initializes a contract.
        @param transaction_id: the id of the transaction this contract is used for.
        @param amount_in_msat: the amount to be transferred in this contract.
        @param hash_x: the hash of the secret x in this contract.
        @param hash_r: the hash of the secret r in this contract.
        @param expiration_block_number: the block number of the expiration time of this contract.
        @param attached_channel: the channel associated with this contract.
        @param payer: the payer of this contract.
        @param payee: the payee of this contract.
        """
        assert amount_in_msat > 0

        self._transaction_id = transaction_id
        self._amount_in_msat: int = amount_in_msat
        self._hash_x: int = hash_x
        self._hash_r: int = hash_r
        self._expiration_block_number: int = expiration_block_number
        self._channel_to_notify: cm.Channel = attached_channel
        self._pre_image_x = None
        self._pre_image_r = None
        self._payer = payer
        self._payee = payee
        self._is_valid = False
        self._was_accepted = False
        self._money_to_transfer_to_payee = 0

        FUNCTION_COLLECTOR_INSTANCE.append(self._on_expired, expiration_block_number)

    def _on_expired(self):
        """
        Called upon contract expiration.
        """
        assert self.is_expired

    @property
    def is_expired(self):
        """
        True iff this contract is expired.
        """
        return BLOCKCHAIN_INSTANCE.block_number >= self._expiration_block_number

    @property
    def expiration_block_number(self):
        return self._expiration_block_number

    @property
    def transaction_id(self) -> int:
        return self._transaction_id

    @property
    def amount_in_msat(self) -> int:
        return self._amount_in_msat

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
        """
        @return: the pre image of `hash_x` - defaults to `None` and changes if someone reports its pre image.
        """
        return self._pre_image_x

    @property
    def pre_image_r(self):
        """
        @return: the pre image of `hash_r` - defaults to `None` and changes if someone reports its pre image.
        """
        return self._pre_image_r

    @property
    def payer(self):
        return self._payer

    @property
    def payee(self):
        return self._payee

    @property
    def transfer_amount_to_payee(self):
        """
        @return: the amount the `payee` should get from `payer`, default is 0, might change when contract is concluded.
        """
        return self._money_to_transfer_to_payee

    @property
    def is_valid(self):
        return self._is_valid

    def invalidate(self):
        """
        Invalidates this contract (means it can no longer be used for transferring)
        """
        self._is_valid = False

    def report_x(self, x: str):
        """
        Used to report the pre image of the `hash_x` given in the constructor.
        """
        assert not self.is_expired
        assert self._is_valid
        assert self._pre_image_x is None and self._pre_image_r is None
        assert hash(x) == self.hash_x
        self._pre_image_x = x

    def report_r(self, r: str):
        """
        Used to report the pre image of the `hash_r` given in the constructor.
        """
        assert not self.is_expired
        assert self._is_valid
        assert self._pre_image_x is None and self._pre_image_r is None
        assert hash(r) == self.hash_r
        self._pre_image_r = r

    def accept_contract(self):
        """
        Used to accept the contract by other party (payee) - if not accepted, the contract in invalid and as such can't be used
        for transferring money.
        """
        if self._was_accepted:
            return
        self._was_accepted = True
        self._is_valid = True


class ContractForward(Contract_HTLC):
    """
    Class to represent a forward contract ('classic' htlc) in the lightning network.
    """
    def __init__(self, transaction_id: int, amount_in_msat: int, hash_x: int, hash_r: int, expiration_block_number: int,
                 attached_channel: cm.Channel, payer: 'ln.LightningNode', payee: 'ln.LightningNode'):
        super().__init__(transaction_id, amount_in_msat, hash_x, hash_r, expiration_block_number, attached_channel, payer, payee)

    def _on_expired(self):
        if self._pre_image_r or self._pre_image_x or not self._channel_to_notify.is_open or not self._is_valid:
            return
        super()._on_expired()

        self._channel_to_notify.notify_of_end_of_contract(self)

    def report_x(self, x: str):
        super().report_x(x)
        self._money_to_transfer_to_payee = self.amount_in_msat
        self.attached_channel.notify_of_end_of_contract(self)

    def report_r(self, r: str):
        super().report_r(r)
        self.attached_channel.notify_of_end_of_contract(self)


class ContractCancellation(Contract_HTLC):
    def __init__(self, transaction_id: int, amount_in_msat: int, hash_x: int, hash_r: int, expiration_block_number: int,
                 attached_channel: cm.Channel, payer: 'ln.LightningNode', payee: 'ln.LightningNode'):
        super().__init__(transaction_id, amount_in_msat, hash_x, hash_r, expiration_block_number, attached_channel, payer, payee)

    def _on_expired(self):
        if self._pre_image_r or self._pre_image_x or not self._channel_to_notify.is_open or not self._is_valid:
            return
        super()._on_expired()

        self._money_to_transfer_to_payee = self.amount_in_msat
        self._channel_to_notify.notify_of_end_of_contract(self)
        self.payee.notify_of_cancellation_contract_payment(self)

    def report_x(self, x: str):
        super().report_x(x)
        self.attached_channel.notify_of_end_of_contract(self)

    def report_r(self, r: str):
        super().report_r(r)
        self.attached_channel.notify_of_end_of_contract(self)
