import pytest  # type: ignore
from unittest.mock import Mock
from typing import Callable, List
from ex2 import Node, Block, PublicKey, BlockHash
import ecdsa  # type: ignore


@pytest.fixture  # type: ignore
def alice() -> Node:
    return Node()


@pytest.fixture  # type: ignore
def bob() -> Node:
    return Node()


@pytest.fixture  # type: ignore
def charlie() -> Node:
    return Node()


@pytest.fixture  # type: ignore
def evil_node_maker() -> Callable[[List[Block]], Mock]:
    def factory(chain: List[Block]) -> Mock:
        evil_node = Mock()
        block_dict = {block.get_block_hash(): block for block in chain}
        evil_node.get_latest_hash.return_value = chain[-1].get_block_hash()

        def my_get_block(block_hash: BlockHash) -> Block:
            if block_hash in block_dict:
                return block_dict[block_hash]
            raise ValueError

        evil_node.get_block.side_effect = my_get_block

        return evil_node

    return factory


@pytest.fixture  # type: ignore
def make_key() -> Callable[[], PublicKey]:
    def factory() -> PublicKey:
        private_key = ecdsa.SigningKey.generate()
        return PublicKey(private_key.get_verifying_key().to_der())

    return factory
