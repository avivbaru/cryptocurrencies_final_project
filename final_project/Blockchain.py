from Contract_HTLC import *
from LightningChannel import *


class Singleton(type):
    _instance = None

    def __call__(cls, *args, **kwargs):
        if cls != cls._instance:
            cls._instance = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instance


class BlockChain(metaclass=Singleton):
    def __init__(self):
        self._block_number = 0
        self._open_channels: Dict[str, ChannelManager] = {}
        self._closed_channels: Dict[str, ChannelManager] = {}
        self._balances: Dict[str, int] = {}

    @property
    def block_number(self):
        return self._block_number

    def wait_k_blocks(self, k):
        for i in range(k):
            self._block_number += 1
            # notify all of block mined

        # TODO: maybe make this not immediate (one by one)
        # can have a subscribe method that calls all objects that called it with a new state (every time)

    def add_channel(self, channel: ChannelManager):
        self._open_channels[channel.channel_state.channel_data.address] = channel

    def close_channel(self, message_state: MessageState):
        channel: ChannelManager = self._open_channels[message_state.channel_address]
        owner2_balance = channel.channel_state.channel_data.total_wei - message_state.owner1_balance
        self._balances[channel.channel_state.channel_data.owner1] = message_state.owner1_balance
        self._balances[channel.channel_state.channel_data.owner2] = owner2_balance
        # TODO: subtract transactions fee

        del self._open_channels[message_state.channel_address]
        self._closed_channels[message_state.channel_address] = channel

    def add_node(self, node: LightningNode, balance: int):
        if node.address in self._balances:
            return

        self._balances[node.address] = balance

    def get_closed_channel_secret_x(self, channel_address):
        if channel_address in self._closed_channels:
            # TODO: change?
            return self._closed_channels[channel_address].secret_x


BLOCKCHAIN_INSTANCE = Singleton(BlockChain)
