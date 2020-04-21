from typing import List, Optional, NewType, Set
import ecdsa  # type: ignore
import hashlib
import secrets

PublicKey = NewType('PublicKey', bytes)
Signature = NewType('Signature', bytes)
BlockHash = NewType('BlockHash', bytes)  # This will be the hash of a block
TxID = NewType("TxID", bytes)  # this will be a hash of a transaction

# these are the bytes written as the prev_block_hash of the 1st block.
GENESIS_BLOCK_PREV = BlockHash(b"Genesis")

BLOCK_SIZE = 10  # The maximal size of a block. Larger blocks are illegal.


class Transaction:
    """Represents a transaction that moves a single coin.
    A transaction with no source creates money. It will only be created by the miner of a block.
    Instead of a signature, it should have 48 random bytes."""

    def __init__(self, output: PublicKey, tx_input: Optional[TxID], signature: Signature) -> None:
        self.output: PublicKey = output  # DO NOT change these field names.
        self.input: Optional[TxID] = tx_input  # DO NOT change these field names.
        self.signature: Signature = signature  # DO NOT change these field names.

    def get_txid(self) -> TxID:
        raise NotImplementedError()


class Block:
    """This class represents a block."""

    def __init__(self, prev_block_hash: BlockHash, transactions: List[Transaction]) -> None:
        """Creates a block with the given previous block hash and a list of transactions.
        Note that this is now part of the API (wasn't in ex1)."""
        raise NotImplementedError()

    def get_block_hash(self) -> BlockHash:
        """Gets the hash of this block."""
        raise NotImplementedError()

    def get_transactions(self) -> List[Transaction]:
        """Returns the list of transactions in this block."""
        raise NotImplementedError()

    def get_prev_block_hash(self) -> BlockHash:
        """Gets the hash of the previous block."""
        raise NotImplementedError()


class Node:
    def __init__(self) -> None:
        """Creates a new node with an empty mempool and no connections to others.
        Blocks mined by this nodes will reward the miner with a single new coin,
        created out of thin air and associated with the mining reward address."""
        raise NotImplementedError()

    def connect(self, other: 'Node') -> None:
        """Connects this node to another node for block and transaction updates.
        Connections are bi-directional, so the other node is connected to this one as well.
        Raises an exception if asked to connect to itself.
        The connection itself does not trigger updates about the mempool,
        but nodes instantly notify of their latest block to each other."""
        raise NotImplementedError()

    def disconnect_from(self, other: 'Node') -> None:
        """Disconnects this node from the other node. If the two were not connected, then nothing happens."""
        raise NotImplementedError()

    def get_connections(self) -> Set['Node']:
        """Returns a set of the connections of this node."""
        raise NotImplementedError()

    def add_transaction_to_mempool(self, transaction: Transaction) -> bool:
        """
        This function inserts the given transaction to the mempool. It is used by a Node's connections to inform
        it of a new transaction.
        It will return False iff any of the following conditions hold:
        (i) The transaction is invalid (the signature fails).
        (ii) The source doesn't have the coin that he tries to spend.
        (iii) There is contradicting tx in the mempool.
        """
        raise NotImplementedError()

    def notify_of_block(self, block_hash: BlockHash, sender: 'Node') -> None:
        """
        This method is used by a node's connection to inform it that it has learned of a
        new block (or created a new block). If the block is unknown to the current Node, the block is requested.
        We assume the sender of the message is specified, so that the node can choose to request this block if
        it wishes to do so.
        If it is part of a longer unknown chain, these blocks are requested as well, until reaching a known block.
        Upon receiving new blocks, they are processed and and checked for validity (check all signatures, hashes,
        block size, etc).
        If the block is on the longest chain, the mempool and UTxO set change accordingly.
        If the block is indeed the tip of the longest chain,
        a notification of this block is sent to the neighboring nodes of this node.
        No need to notify of previous blocks -- the nodes will fetch them if needed.

        A reorg may be triggered by this block's introduction. In this case the UTxO set is rolled back to the split point,
        and then rolled forward along the new branch.
        The mempool is similarly emptied of transactions that cannot be executed now.
        """
        raise NotImplementedError()

    def mine_block(self) -> BlockHash:
        """"
        This function allows the node to create a single block. It is called externally by the tests.
        The block should contain BLOCK_SIZE transactions (unless there aren't enough in the mempool). Of these,
        BLOCK_SIZE-1 transactions come from the mempool and one addtional transaction will be included that creates
        money and adds it to the address of this miner.
        Money creation transactions have None as their input, and instead of a signature, contain 48 random bytes.
        If a new block is created, all connections of this node are notified by calling their notify_of_block() method.
        The method returns the new block hash.
        """
        raise NotImplementedError()

    def get_block(self, block_hash: BlockHash) -> Block:
        """
        This function returns a block object given its hash.
        If the block doesnt exist, a ValueError is raised. Make sure to throw the correct exception here!
        """
        raise NotImplementedError()

    def get_latest_hash(self) -> BlockHash:
        """
        This function returns the hash of the block that is the current tip of the longest chain.
        If no blocks were created, return GENESIS_BLOCK_PREV.
        """
        raise NotImplementedError()

    def get_mempool(self) -> List[Transaction]:
        """
        This function returns the list of transactions that are waiting to be included in blocks.
        """
        raise NotImplementedError()

    def get_utxo(self) -> List[Transaction]:
        """
        This function returns the list of unspent transactions.
        """
        raise NotImplementedError()

    def create_transaction(self, target: PublicKey) -> Optional[Transaction]:
        """
        This function returns a signed transaction that moves an unspent coin to the target.
        It chooses the coin based on the unspent coins that this node owns.
        If the node already tried to spend a specific coin, and such a transaction exists in its mempool,
        but it did not yet get into the blockchain then the node should'nt try to spend it again until clear_mempool() is
        called -- which will wipe the mempool and thus allow the node to attempt these re-spends.
        The method returns None if there are no outputs that have not been spent already.
        The transaction is added to the mempool (and as a result it is also published to connected nodes).
        """
        raise NotImplementedError()

    def clear_mempool(self) -> None:
        """
        Clears this nodes mempool. All transactions waiting to be entered into the next block are cleared.
        """
        raise NotImplementedError()

    def get_balance(self) -> int:
        """
        This function returns the number of coins that this node owns according to its view of the blockchain.
        Coins that the node owned and sent away will still be considered as part of the balance until the spending
        transaction is in the blockchain.
        """
        raise NotImplementedError()

    def get_address(self) -> PublicKey:
        """
        This function returns the public address of this node in DER format (follow the code snippet in the pdf of ex1).
        """
        raise NotImplementedError()


"""
Importing this file should NOT execute code. It should only create definitions for the objects above.
Write any tests you have in a different file.
You may add additional methods, classes and files but be sure no to change the signatures of methods
included in this template.
"""
