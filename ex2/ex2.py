from typing import List, Optional, NewType, Set, Dict, Tuple
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

        self.id_value = self.output + self.signature if tx_input is None else self.output + self.signature + self.input
        self.id = TxID(hashlib.sha256(self.id_value).digest())

    def get_txid(self) -> TxID:
        """Returns the identifier of this transaction. This is the sha256 of the transaction contents."""
        return self.id


class Block:
    """This class represents a block."""

    def __init__(self, prev_block_hash: BlockHash, transactions: List[Transaction]) -> None:
        """Creates a block with the given previous block hash and a list of transactions.
        Note that this is now part of the API (wasn't in ex1)."""
        self.transactions = transactions
        self.previous_block_hash = prev_block_hash
        self.my_hash = Block.get_hash(self.previous_block_hash, self.transactions)

    @staticmethod
    def get_hash(previous_block_hash, transactions):
        temp_hash = previous_block_hash
        for transaction in transactions:
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


class Node:
    def __init__(self) -> None:
        """Creates a new node with an empty mempool and no connections to others.
        Blocks mined by this nodes will reward the miner with a single new coin,
        created out of thin air and associated with the mining reward address."""
        self.mempool: List[Transaction] = []
        self.blockchain: List[Block] = []
        self.connections: Set[Node] = set()
        self.unspent_transactions = {}
        self.block_hash_to_block = {}
        self._private_key = ecdsa.SigningKey.generate()
        self.public_key = PublicKey(self._private_key.get_verifying_key().to_der())
        self._my_unspent_transactions: Set[TxID] = set()
        self._transactions_used_since_last_update: Set[TxID] = set()

    class _block_verification_model:
        def __init__(self, block_hash, block):
            self.block_hash = block_hash
            self.block = block

    def connect(self, other: 'Node') -> None:
        """Connects this node to another node for block and transaction updates.
        Connections are bi-directional, so the other node is connected to this one as well.
        Raises an exception if asked to connect to itself.
        The connection itself does not trigger updates about the mempool,
        but nodes instantly notify of their latest block to each other."""
        if other is self:
            raise Exception("Could not connect to myself")
        if other not in self.connections:
            self.connections.add(other)
            other.connect(self)
            other.notify_of_block(self.get_latest_hash(), self)

    def disconnect_from(self, other: 'Node') -> None:
        """Disconnects this node from the other node. If the two were not connected, then nothing happens."""
        if other in self.connections:
            self.connections.remove(other)
            other.disconnect_from(self)

    def get_connections(self) -> Set['Node']:
        """Returns a set of the connections of this node."""
        return self.connections

    def add_transaction_to_mempool(self, transaction: Transaction) -> bool:
        """
        This function inserts the given transaction to the mempool. It is used by a Node's connections to inform
        it of a new transaction.
        It will return False iff any of the following conditions hold:
        (i) The transaction is invalid (the signature fails).
        (ii) The source doesn't have the coin that he tries to spend.
        (iii) There is contradicting tx in the mempool.
        """
        is_transaction_ok = (
                Node._is_transaction_valid(transaction, self.unspent_transactions) and
                Node._source_has_money_for(transaction, self.unspent_transactions) and
                Node._no_conflicts_for(transaction, self.mempool))
        if is_transaction_ok:
            self.mempool.append(transaction)
            for node in self.connections:
                node.add_transaction_to_mempool(transaction)

        return is_transaction_ok

    @staticmethod
    def _is_transaction_valid(transaction: Transaction, unspent_transactions) -> bool:
        if transaction.input is None:
            return False

        transaction_pay = unspent_transactions.get(transaction.input, None)
        try:
            return ecdsa.VerifyingKey.from_der(transaction_pay.output).verify(transaction.signature,
                                                                              transaction.output + transaction.input)
        except:
            return False

    @staticmethod
    def _source_has_money_for(transaction: Transaction, unspent_transactions) -> bool:
        return transaction.input in unspent_transactions

    @staticmethod
    def _no_conflicts_for(transaction: Transaction, current_transactions: List[Transaction]) -> bool:
        for unblocked_transaction in current_transactions:
            if unblocked_transaction.input == transaction.input:
                return False

        return True

    def _verify_block_hash(self, block: Block) -> bool:
        return Block.get_hash(block.get_prev_block_hash(), block.get_transactions()) == block.get_block_hash()

    def _verify_block_receive(self, block_hash: BlockHash, block: Block) -> bool:
        return block_hash == block.get_block_hash()

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
        if block_hash in self.block_hash_to_block:
            return
        try:
            current_block = sender.get_block(block_hash)
            if not self._verify_block_receive(block_hash, current_block):
                return
            blocks_from_sender = [current_block]
            while current_block.get_prev_block_hash() not in self.block_hash_to_block and \
                    current_block.get_prev_block_hash() != GENESIS_BLOCK_PREV:
                prev_block_hash = current_block.get_prev_block_hash()
                current_block = sender.get_block(prev_block_hash)
                if not self._verify_block_receive(prev_block_hash, current_block) or current_block in blocks_from_sender:
                    return
                blocks_from_sender.append(current_block)
        except ValueError as e:
            return

        blocks_from_sender.reverse()
        split_block = self.block_hash_to_block.get(current_block.get_prev_block_hash())
        prev_index = self.blockchain.index(split_block) + 1 if split_block else 0
        new_state = self._get_new_blockchain_state(blocks_from_sender, prev_index)
        if new_state is not None:
            self.blockchain, self.unspent_transactions = new_state
            self.block_hash_to_block = {}
            for block in self.blockchain:
                self.block_hash_to_block[block.get_block_hash()] = block

            self._update_wallet_state()
            self._notifiy_all_my_friends_of(self.get_latest_hash())

    def _get_new_blockchain_state(self, blockchain: List[Block], split_block_index: int) -> Optional[
        Tuple[List, Dict]]:
        def get_new_state_no_length_check(blockchain: List[Block], new_unspent_transactions: Dict):
            for block_index, block in enumerate(blockchain):
                current_unspent_transactions = {}
                current_transactions_to_delete = set()
                blocks_transactions = block.get_transactions()
                if not self._verify_block_hash(block) or len(blocks_transactions) > BLOCK_SIZE:
                    return blockchain[:block_index], new_unspent_transactions

                number_of_money_creation_transaction = 0
                for transaction in blocks_transactions:
                    current_unspent_transactions[transaction.get_txid()] = transaction

                    if transaction.input is None:
                        number_of_money_creation_transaction += 1
                    elif transaction.input not in new_unspent_transactions or not Node._is_transaction_valid(
                            transaction, new_unspent_transactions):
                        return blockchain[:block_index], new_unspent_transactions
                    else:
                        current_transactions_to_delete.add(transaction.input)

                if current_transactions_to_delete.intersection(set(current_unspent_transactions.keys())) or \
                        number_of_money_creation_transaction != 1:
                    return blockchain[:block_index], new_unspent_transactions

                new_unspent_transactions = {**new_unspent_transactions, **current_unspent_transactions}

                for transaction_id in current_transactions_to_delete:
                    del new_unspent_transactions[transaction_id]
            return blockchain, new_unspent_transactions
        
        new_unspent_transactions = self._get_unspent_until(split_block_index)
        new_blockchain, new_unspent_transactions = get_new_state_no_length_check(blockchain, new_unspent_transactions)

        if len(new_blockchain) + split_block_index > len(self.blockchain):
            return self.blockchain[:split_block_index] + new_blockchain, new_unspent_transactions
        return None

    def _notifiy_all_my_friends_of(self, block_hash: BlockHash):
        for node in self.connections:
            node.notify_of_block(block_hash, self)

    def _get_unspent_until(self, split_block_index: int) -> Dict:
        all_transactions = {}
        for block in self.blockchain:
            for transaction in block.get_transactions():
                all_transactions[transaction.get_txid()] = transaction
        new_unspent_transactions = self.unspent_transactions.copy()
        for my_block in reversed(self.blockchain[split_block_index:]):
            current_block_transactions = my_block.get_transactions()

            for transaction in current_block_transactions:
                if transaction.get_txid() in new_unspent_transactions:
                    del new_unspent_transactions[transaction.get_txid()]
                if transaction.input is not None and transaction.input not in new_unspent_transactions:
                    new_unspent_transactions[transaction.input] = all_transactions[transaction.input]
        return new_unspent_transactions

    def _update_wallet_state(self):
        self._update_my_unspent_transactions()

        self.mempool = [transaction for transaction in self.mempool
                        if Node._source_has_money_for(transaction, self.unspent_transactions)]

    def _update_my_unspent_transactions(self):
        self._my_unspent_transactions = set()
        for transaction in self.unspent_transactions.values():
            if transaction.output == self.public_key:
                self._my_unspent_transactions.add(transaction.get_txid())

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
        # TODO: ask if there is a situation where we wouldn't create a block
        transactions_for_block = self.mempool[:BLOCK_SIZE - 1]
        self.mempool = self.mempool[BLOCK_SIZE - 1:]
        transactions_for_block.append(self._create_money())

        for transaction in transactions_for_block:
            self.unspent_transactions[transaction.get_txid()] = transaction
            if transaction.input:
                del self.unspent_transactions[transaction.input]
        self._update_my_unspent_transactions()

        prev_block_hash = self.get_latest_hash()
        block_to_add = Block(prev_block_hash, transactions_for_block)
        self.blockchain.append(block_to_add)
        self.block_hash_to_block[block_to_add.get_block_hash()] = block_to_add
        block_hash = block_to_add.get_block_hash()
        self._notifiy_all_my_friends_of(block_hash)
        return block_hash

    def _create_money(self) -> Transaction:
        """
        This function inserts a transaction into the mempool that creates a single coin out of thin air. Instead of a signature,
        this transaction includes a random string of 48 bytes (so that every two creation transactions are different).
        generate these random bytes using secrets.token_bytes(48).
        We assume only the bank calls this function (wallets will never call it).
        """
        signature = secrets.token_bytes(48)
        new_money_transaction = Transaction(self.public_key, None, signature)
        return new_money_transaction

    def get_block(self, block_hash: BlockHash) -> Block:
        """
        This function returns a block object given its hash.
        If the block doesnt exist, a ValueError is raised. Make sure to throw the correct exception here!
        """
        if block_hash in self.block_hash_to_block:
            return self.block_hash_to_block[block_hash]

        raise ValueError("No block found with this hash code.")

    def get_latest_hash(self) -> BlockHash:
        """
        This function returns the hash of the block that is the current tip of the longest chain.
        If no blocks were created, return GENESIS_BLOCK_PREV.
        """
        return self.blockchain[-1].get_block_hash() if self.blockchain else GENESIS_BLOCK_PREV

    def get_mempool(self) -> List[Transaction]:
        """
        This function returns the list of transactions that are waiting to be included in blocks.
        """
        return self.mempool

    def get_utxo(self) -> List[Transaction]:
        """
        This function returns the list of unspent transactions.
        """
        return list(self.unspent_transactions.values())

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
        set_mempool_inputs = {transaction.input for transaction in self.mempool}
        transactions_id_to_use = [transaction_id for transaction_id in self._my_unspent_transactions
                                  if transaction_id not in set_mempool_inputs]
        if transactions_id_to_use:
            transaction_id_to_use = transactions_id_to_use[0]
            signature = Signature(self._private_key.sign(target + transaction_id_to_use))
            transaction = Transaction(target, transaction_id_to_use, signature)
            is_inserted_to_mempool = self.add_transaction_to_mempool(transaction)
            return transaction if is_inserted_to_mempool else None

        return None

    def clear_mempool(self) -> None:
        """
        Clears this nodes mempool. All transactions waiting to be entered into the next block are cleared.
        """
        self.mempool = []

    def get_balance(self) -> int:
        """
        This function returns the number of coins that this node owns according to its view of the blockchain.
        Coins that the node owned and sent away will still be considered as part of the balance until the spending
        transaction is in the blockchain.
        """
        return len(self._my_unspent_transactions)

    def get_address(self) -> PublicKey:
        """
        This function returns the public address of this node in DER format (follow the code snippet in the pdf of ex1).
        """
        return self.public_key


"""
Importing this file should NOT execute code. It should only create definitions for the objects above.
Write any tests you have in a different file.
You may add additional methods, classes and files but be sure no to change the signatures of methods
included in this template.
"""
