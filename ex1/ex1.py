from typing import List, Optional, NewType
import ecdsa  # type: ignore
import hashlib
import secrets

PublicKey = NewType('PublicKey', bytes)
Signature = NewType('Signature', bytes)
BlockHash = NewType('BlockHash', bytes)  # This will be the hash of a block
TxID = NewType("TxID", bytes)  # this will be a hash of a transaction

GENESIS_BLOCK_PREV = BlockHash(b"Genesis")  # these are the bytes written as the prev_block_hash of the 1st block.


class Transaction:
    """Represents a transaction that moves a single coin
    A transaction with no source creates money. It will only be created by the bank."""

    def __init__(self, output: PublicKey, input: Optional[TxID], signature: Signature) -> None:
        self.output: PublicKey = output  # DO NOT change these field names.
        self.input: Optional[TxID] = input  # DO NOT change these field names.
        self.signature: Signature = signature  # DO NOT change these field names.

    def get_txid(self) -> TxID:
        """Returns the identifier of this transaction. This is the sha256 of the transaction contents."""
        raise NotImplementedError()


class Block:
    """This class represents a block."""

    # define the __init__ as you wish

    def get_block_hash(self) -> BlockHash:
        """Gets the hash of this block"""
        raise NotImplementedError()

    def get_transactions(self) -> List[Transaction]:
        """
        returns the list of transactions in this block.
        """
        raise NotImplementedError()

    def get_prev_block_hash(self) -> BlockHash:
        """Gets the hash of the previous block"""
        raise NotImplementedError()


class Bank:
    def __init__(self) -> None:
        """Creates a bank with an empty blockchain and an empty mempool."""
        raise NotImplementedError()

    def add_transaction_to_mempool(self, transaction: Transaction) -> bool:
        """
        This function inserts the given transaction to the mempool.
        It will return False iff any of the following conditions hold:
        (i) the transaction is invalid (the signature fails)
        (ii) the source doesn't have the coin that he tries to spend
        (iii) there is contradicting tx in the mempool.
        """
        raise NotImplementedError()

    def end_day(self, limit: int = 10) -> BlockHash:
        """
         This function tells the bank that the day ended,
         and that the first `limit` transactions in the mempool should be committed to a block.
         If there are fewer than 'limit' transactions in the mempool, a smaller block is created.
         If there are no transactions, an empty block is created.
         The hash of this new block is returned.
         """
        raise NotImplementedError()

    def get_block(self, block_hash: BlockHash) -> Block:
        """
        This function returns a block object given its hash. If the block doesnt exist, an exception is thrown..
        """
        raise NotImplementedError()

    def get_latest_hash(self) -> BlockHash:
        """
        This function returns the last block hash the was created.
        """
        raise NotImplementedError()

    def get_mempool(self) -> List[Transaction]:
        """
        This function returns the list of transactions that didn't enter any block yet.
        """
        raise NotImplementedError()

    def get_utxo(self) -> List[Transaction]:
        """
        This function returns the list of unspent transactions.
        """
        raise NotImplementedError()

    def create_money(self, target: PublicKey) -> None:
        """
        This function inserts a transaction into the mempool that creates a single coin out of thin air. Instead of a signature,
        this transaction includes a random string of 48 bytes (so that every two creation transactions are different).
        generate these random bytes using secrets.token_bytes(48).
        We assume only the bank calls this function (wallets will never call it).
        """
        raise NotImplementedError()


class Wallet:
    """The Wallet class. Each wallet controls a single private key, and has a single corresponding public key (address).
    Wallets keep track of the coins owned by them, and can create transactions to move these coins."""

    def __init__(self) -> None:
        """
        This function generates a new wallet with a new private key.
        """
        raise NotImplementedError()

    def update(self, bank: Bank) -> None:
        """
        This function updates the balance allocated to this wallet by querying the bank.
        Don't read all of the bank's utxo, but rather process the blocks since the last update one at a time.
        For this exercise, there is no need to validate all transactions in the block
        """
        # first build a list of blocks until our latest update.
        raise NotImplementedError()

    def create_transaction(self, target: PublicKey) -> Optional[Transaction]:
        """
        This function returns a signed transaction that moves an unspent coin to the target.
        It chooses the coin based on the unspent coins that this wallet had since the last update.
        If the wallet already spent a specific coin, then he should'nt spend it again until unfreeze_all() is called.
        The method returns None if there are no outputs that have not been spent already.
        """
        raise NotImplementedError()

    def unfreeze_all(self) -> None:
        """
        Allows the wallet to try to re-spend outputs that it created transactions for (unless these outputs already
        made it into the blockchain).
        """
        raise NotImplementedError()

    def get_balance(self) -> int:
        """
        This function returns the number of coins that this wallet has.
        It will return the balance that is relevant until the last call to update.
        Coins that the wallet owned and sent away will still be considered as part of the balance until the spending
        transaction is in the blockchain.
        """
        raise NotImplementedError()

    def get_address(self) -> PublicKey:
        """
        This function returns the public address of this wallet in DER format (follow the code snippet in the pdf).
        """
        raise NotImplementedError()

# importing this file should NOT execute code. It should only create definitions for the objects above.
# Write any tests you have in a different file.
# You may add additional methods, classes and files but be sure no to change the signatures of methods included in this template.
