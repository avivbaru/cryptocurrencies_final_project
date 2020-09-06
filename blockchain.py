import contract_htlc as cn
import lightning_node as lc
import channel_manager as cm
from typing import Dict, Optional


class BlockChain:
    """
    Class to represent Bitcoin's blockchain (as a simplification).
    """
    def __init__(self):
        self.init_parameters()

    def init_parameters(self):
        """
        Used to reset this instance.
        """
        self._block_number = 0
        self._open_channels: Dict[str, 'cm.Channel'] = {}
        self._channels_to_htlcs: Dict[str, 'cn.Contract_HTLC'] = {}
        self._nodes_addresses_to_balances: Dict[str, int] = {}
        self._hash_image_to_pre_images: Dict[int, str] = {}
        self._fee = 0.1

    @property
    def block_number(self):
        """
        @return: the current block number in the blockchain.
        """
        return self._block_number

    @property
    def total_balance(self) -> int:
        """
        @return: returns the total balance currently held in the blockchain.
        """
        return int(sum(self._nodes_addresses_to_balances.values()))

    @property
    def fee(self):
        """
        @return: the fee (as a percentage in the range [0 - 1]) the blockchain claims upon a transaction.
        """
        return self._fee

    def get_balance_for_node(self, node):
        """
        @return: returns the current balance of `node`.
        """
        return self._nodes_addresses_to_balances.get(node.address)

    def wait_k_blocks(self, k):
        """
        Increments the current block number by `k` blocks.
        """
        self._block_number += k

    def add_channel(self, channel: 'cm.Channel'):
        """
        Adds channel `channel` to the blockchain.
        """
        self.apply_transaction(channel.channel_state.channel_data.owner1, channel.channel_state.message_state.owner1_balance)
        self._open_channels[channel.channel_state.channel_data.address] = channel

    def close_channel(self, message_state: 'cm.MessageState'):
        """
        Closes the channel that corresponds to the given `message_state`.
        """
        channel: cm.Channel = self._open_channels[message_state.channel_address]
        owner2_balance = channel.channel_state.channel_data.total_msat - message_state.owner1_balance
        self._nodes_addresses_to_balances[channel.channel_state.channel_data.owner1.address] += \
            message_state.owner1_balance * (1 - self._fee)
        self._nodes_addresses_to_balances[channel.channel_state.channel_data.owner2.address] += owner2_balance * (1 - self._fee)

        del self._open_channels[message_state.channel_address]
        # if contract:
        #     self._channels_to_htlcs[message_state.channel_address] = contract

    def report_pre_image(self, pre_image: str):
        """
        Used for reporting the given `pre_image` to the blockchain so it can be obtained later by other nodes in the network.
        """
        self._hash_image_to_pre_images[hash(pre_image)] = pre_image

    def add_node(self, node: 'lc.LightningNode', balance: int):
        """
        Adds the given `node` to the blockchain with the given initial balance `balance`
        """
        if node.address in self._nodes_addresses_to_balances:
            return

        self._nodes_addresses_to_balances[node.address] = balance

    def get_pre_image_if_exists_onchain(self, hash_image: int) -> Optional[str]:
        """
        @return: the pre image of `hash_image` if exists in the blockchain, `None` otherwise.
        """
        if hash_image in self._hash_image_to_pre_images:
            return self._hash_image_to_pre_images[hash_image]
        return None

    def apply_transaction(self, node: 'lc.LightningNode', amount_in_msat: int):
        """
        @return: applies (takes fee and reduces balance) a transaction with amount `amount_in_msat` with `node` as the sender.
        """
        self._nodes_addresses_to_balances[node.address] -= amount_in_msat * (1 + self._fee)
        assert self._nodes_addresses_to_balances[node.address] >= 0

