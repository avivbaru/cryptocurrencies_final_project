from Contract_HTLC import *

class Contract_HTLC_GP(Contract_HTLC):
    def __init__(self, owner1_balance_delta, hash_image: int, expiration_block_number: int, attached_channel: cm.ChannelManager,
                 owner1: 'ln.LightningNode', owner2: 'ln.LightningNode', penalty: int):
        super().__init__(owner1_balance_delta, hash_image, expiration_block_number, attached_channel, owner1, owner2)

        self._penalty = penalty

    @property
    def penalty(self):
        return self._penalty

    @property
    def additional_delta_for_locked_funds(self) -> int:
        return -self._penalty

    def resolve_griefed_contract(self):
        super()._owner1_balance_delta += self._penalty
        super().resolve_griefed_contract()
