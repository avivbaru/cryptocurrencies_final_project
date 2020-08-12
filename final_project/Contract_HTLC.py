import Blockchain


class MessageState:
    def __init__(self, owner1_balance, serial, channel_address=None):
        self.owner1_balance = owner1_balance
        self._serial = serial
        self.channel_address = channel_address
        self._valid = False

    @property
    def serial_number(self):
        return self._serial

    @property
    def is_valid(self):
        return self._valid
# TODO: move MessageState out of here

class Contract_HTLC:
    def __init__(self, owner1_balance_delta, hash_image: int, expiration_block_number: int):
        self._owner1_balance_delta = owner1_balance_delta
        self._hash_image: int = hash_image
        self._expiration_block_number: int = expiration_block_number
        self._validated = False

    @property
    def is_expired(self):
        return Blockchain.BLOCKCHAIN_INSTANCE.block_number >= self._expiration_block_number

    @property
    def owner1_balance_delta(self):
        return self._owner1_balance_delta

    @property
    def hash_image(self):
        return self._hash_image

    @property
    def is_valid(self):
        return self._validated

    def validate(self, pre_image: str) -> bool:
        if self.is_expired:
            return False

        if hash(pre_image) == self._hash_image:
            self._validated = True
            return True

        return False

