from typing import List, Optional, NewType, Set
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

        self.id_value = self.output + self.signature if input is None else self.output + self.signature + self.input
        self.id = TxID(hashlib.sha256(self.id_value).digest())

    def get_txid(self) -> TxID:
        """Returns the identifier of this transaction. This is the sha256 of the transaction contents."""
        return self.id

class Block:
    """This class represents a block."""

    def __init__(self, transactions: List[Transaction], previous_block_hash: BlockHash):
        self.transactions = transactions
        self.previous_block_hash = previous_block_hash
        self.my_hash = self._get_hash()

    def _get_hash(self):
        temp_hash = self.previous_block_hash
        for transaction in self.transactions:
            temp_hash += transaction.get_txid()

        return BlockHash(hashlib.sha256(temp_hash).digest())

    def get_block_hash(self) -> BlockHash:
        """Gets the hash of this block"""
        return self.my_hash

    def get_transactions(self) -> List[Transaction]:
        """
        returns the list of transactions in this block.
        """
        return self.transactions

    def get_prev_block_hash(self) -> BlockHash:
        """Gets the hash of the previous block"""
        return self.previous_block_hash

class Bank:
    def __init__(self) -> None:
        """Creates a bank with an empty blockchain and an empty mempool."""
        self.mempool: List[Transaction] = []
        self.blockchain: List[Block] = []
        self.unspent_transactions = {}
        self.block_hash_to_block = {}

    def add_transaction_to_mempool(self, transaction: Transaction) -> bool:
        """
        This function inserts the given transaction to the mempool.
        It will return False iff any of the following conditions hold:
        (i) the transaction is invalid (the signature fails)
        (ii) the source doesn't have the coin that he tries to spend
        (iii) there is contradicting tx in the mempool.
        """
        is_transaction_ok = (self._is_transaction_valid(transaction) and self._source_has_money_for(transaction) and
                             self._no_conflicts_for(transaction))
        if is_transaction_ok:
            self.mempool.append(transaction)

        return is_transaction_ok

    def _is_transaction_valid(self, transaction: Transaction) -> bool:
        if transaction.input is None:
            return False

        transaction_pay = self.unspent_transactions.get(transaction.input, None)
        try:
            return ecdsa.VerifyingKey.from_der(transaction_pay.output).verify(transaction.signature,
                                                                         transaction.output + transaction.input)
        except:
            return False

    def _source_has_money_for(self, transaction: Transaction) -> bool:
        return transaction.input in self.unspent_transactions

    def _no_conflicts_for(self, transaction: Transaction) -> bool:
        for unblocked_transaction in self.mempool:
            if unblocked_transaction.input == transaction.input:
                return False

        return True

    def end_day(self, limit: int = 10) -> BlockHash:
        """
         This function tells the bank that the day ended,
         and that the first `limit` transactions in the mempool should be committed to a block.
         If there are fewer than 'limit' transactions in the mempool, a smaller block is created.
         If there are no transactions, an empty block is created.
         The hash of this new block is returned.
         """
        transactions_for_block = self.mempool[:limit]
        for transaction in transactions_for_block:
            self.unspent_transactions[transaction.get_txid()] = transaction
            if transaction.input:
                del self.unspent_transactions[transaction.input]

        prev_block_hash = self.blockchain[-1].get_block_hash() if self.blockchain else GENESIS_BLOCK_PREV
        block_to_add = Block(transactions_for_block, prev_block_hash)
        self.blockchain.append(block_to_add)
        self.block_hash_to_block[block_to_add.get_block_hash()] = block_to_add
        self.mempool = self.mempool[limit:]
        return block_to_add.get_block_hash()

    def get_block(self, block_hash: BlockHash) -> Block:
        """
        This function returns a block object given its hash. If the block doesnt exist, an exception is thrown..
        """
        if block_hash in self.block_hash_to_block:
            return self.block_hash_to_block[block_hash]

        raise Exception("No block found with this hash code.")

    def get_latest_hash(self) -> BlockHash:
        """
        This function returns the last block hash the was created.
        """
        return self.blockchain[-1].get_block_hash() if self.blockchain else GENESIS_BLOCK_PREV

    def get_mempool(self) -> List[Transaction]:
        """
        This function returns the list of transactions that didn't enter any block yet.
        """
        return self.mempool

    def get_utxo(self) -> List[Transaction]:
        """
        This function returns the list of unspent transactions.
        """
        return list(self.unspent_transactions.values())

    def create_money(self, target: PublicKey) -> None:
        """
        This function inserts a transaction into the mempool that creates a single coin out of thin air. Instead of a signature,
        this transaction includes a random string of 48 bytes (so that every two creation transactions are different).
        generate these random bytes using secrets.token_bytes(48).
        We assume only the bank calls this function (wallets will never call it).
        """
        signature = secrets.token_bytes(48)
        new_money_transaction = Transaction(target, None, signature)
        self.mempool.append(new_money_transaction)

class Wallet:
    """The Wallet class. Each wallet controls a single private key, and has a single corresponding public key (address).
    Wallets keep track of the coins owned by them, and can create transactions to move these coins."""

    def __init__(self) -> None:
        """
        This function generates a new wallet with a new private key.
        """
        self._private_key = ecdsa.SigningKey.generate()
        self.public_key = PublicKey(self._private_key.get_verifying_key().to_der())
        self._blockchain: List[Block] = []
        self._unspent_transactions: Set[TxID] = set()
        self._transactions_used_since_last_update: Set[TxID] = set()

    def update(self, bank: Bank) -> None:
        """
        This function updates the balance allocated to this wallet by querying the bank.
        Don't read all of the bank's utxo, but rather process the blocks since the last update one at a time.
        For this exercise, there is no need to validate all transactions in the block
        """
        # first build a list of blocks until our latest update.
        block_hash = bank.get_latest_hash()
        current_latest_hash = self._blockchain[-1].get_block_hash() if self._blockchain else None
        updates_blockchain = []
        while block_hash != current_latest_hash and block_hash != GENESIS_BLOCK_PREV:
            block = bank.get_block(block_hash)
            for transaction in block.get_transactions():
                if transaction.input in self._unspent_transactions:
                    self._unspent_transactions.remove(transaction.input)
                if transaction.output == self.public_key:
                    self._unspent_transactions.add(transaction.get_txid())
            updates_blockchain.append(block)
            block_hash = block.get_prev_block_hash()
        updates_blockchain.reverse()
        self._blockchain += updates_blockchain
        self._transactions_used_since_last_update.intersection_update(self._unspent_transactions)

    def create_transaction(self, target: PublicKey) -> Optional[Transaction]:
        """
        This function returns a signed transaction that moves an unspent coin to the target.
        It chooses the coin based on the unspent coins that this wallet had since the last update.
        If the wallet already spent a specific coin, then he should'nt spend it again until unfreeze_all() is called.
        The method returns None if there are no outputs that have not been spent already.
        """
        transactions_id_to_use = self._unspent_transactions.difference(self._transactions_used_since_last_update)
        if transactions_id_to_use:
            transaction_id_to_use = transactions_id_to_use.pop()
            self._transactions_used_since_last_update.add(transaction_id_to_use)
            signature = Signature(self._private_key.sign(target + transaction_id_to_use))
            return Transaction(target, transaction_id_to_use, signature)
        return None

    def unfreeze_all(self) -> None:
        """
        Allows the wallet to try to re-spend outputs that it created transactions for (unless these outputs already
        made it into the blockchain).
        """
        self._transactions_used_since_last_update = set()

    def get_balance(self) -> int:
        """
        This function returns the number of coins that this wallet has.
        It will return the balance that is relevant until the last call to update.
        Coins that the wallet owned and sent away will still be considered as part of the balance until the spending
        transaction is in the blockchain.
        """
        return len(self._unspent_transactions)

    def get_address(self) -> PublicKey:
        """
        This function returns the public address of this wallet in DER format (follow the code snippet in the pdf).
        """
        return self.public_key

# importing this file should NOT execute code. It should only create definitions for the objects above.
# Write any tests you have in a different file.
# You may add additional methods, classes and files but be sure no to change the signatures of methods included in this template.
