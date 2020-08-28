from contract_htlc import *
import lightning_node as lc


class Contract_HTLC_GP(Contract_HTLC):
    def __init__(self, amount_in_wei: int, hash_image: int, expiration_block_number: int,
                 attached_channel: cm.ChannelManager,
                 owner1: 'ln.LightningNode', owner2: 'ln.LightningNode', penalty: int):
        super().__init__(amount_in_wei, hash_image, expiration_block_number, attached_channel, owner1, owner2)

        self._penalty = penalty
        assert super().attached_channel.amount_owner2_can_transfer_to_owner1 >= penalty

    @property
    def penalty(self):
        return self._penalty

    def additional_delta_for_locked_funds(self, owner: 'lc.LightningNode') -> int:
        if owner.address == super().receiver:
            return self._penalty
        return 0

    # def resolve_griefed_contract(self):
    #     super()._owner1_balance_delta = self._penalty
    #     super().resolve_griefed_contract()
