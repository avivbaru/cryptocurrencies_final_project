import web3
import time
import eth_account.messages
from contracts_variables import COMPILED_CHANNEL, ABI_CHANNEL
import web3.contract
from web3.contract import Contract
from typing import Dict, AnyStr

SIG_TYPES = ['uint256', 'int256', 'address'] # the types of messages
w3 = web3.Web3(web3.HTTPProvider("http://127.0.0.1:7545"))
APPEAL_PERIOD = 3  # the appeal period in blocks.
STARTING_SERIAL = 0 # first serial number


class ChannelData:
    def __init__(self, channel_obj: Contract, owner1=None, owner2=None, total_wei=None):
        self.owner1 = owner1
        self.owner2 = owner2
        self.channel_obj: Contract = channel_obj
        self.total_wei = total_wei


class MessageState:
    def __init__(self, balance, serial, sig, channel_address):
        self.serial = serial
        self.sig = sig
        # Assume balance is the amount of wei for the Node holding this message state
        self.balance = balance
        self.channel_address = channel_address


class ChannelState:
    def __init__(self, channel_data: ChannelData, message_state: MessageState=None):
        self.channel_data: ChannelData = channel_data
        self.message_state: MessageState = message_state


class LightningNode:
    def __init__(self, my_account):
        """
        Initializes a new node that uses the given local ethereum account to move money
        :param my_account: The account's address.
        """
        self._account_address = my_account
        self._channels: Dict[str, ChannelState] = {}
        self._txn_dict = {'from': self._account_address}

    def get_address(self):
        """
        Returns the address of this node on the blockchain (its ethereum wallet).
        """
        return self._account_address

    def establish_channel(self, other_party_address, amount_in_wei):
        """
        Sets up a channel with another user at the given ethereum address.
        Returns the address of the contract on the blockchain.
        :param other_party_address: the other channel member
        :param amount_in_wei: the amount to send to the channel
        :return: returns the contract address on the blockchain
        """
        contract_factory = w3.eth.contract(abi=ABI_CHANNEL, bytecode=COMPILED_CHANNEL["object"])

        txn_dict = {'from': self._account_address, 'value': amount_in_wei}
        tx_hash = contract_factory.constructor(other_party_address, APPEAL_PERIOD).transact(txn_dict)

        tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)

        contract = w3.eth.contract(address=tx_receipt.contractAddress, abi=ABI_CHANNEL)
        channel_data = ChannelData(contract, self._account_address, other_party_address, amount_in_wei)
        self._channels[contract.address] = ChannelState(channel_data)
        return contract.address

    def notify_of_channel(self, contract_address):
        """
        A function that is called when someone created a channel with you and wants to let you know.
        :param contract_address: channel address
        """
        contract = w3.eth.contract(address=contract_address, abi=ABI_CHANNEL)
        balance = contract.functions.get_current_balance().call()
        # Get owner1 public address from the channel contract
        owner1 = contract.functions.get_owner1_address().call()
        channel_data = ChannelData(contract, owner1, self._account_address, balance)
        self._channels[contract_address] = ChannelState(channel_data)

    @staticmethod
    def check_channel_address(func):
        """
        Decorator for Node method. Check if the Node know the channel address argument.
        """
        def wrapper(self, address, *args):
            if address in self._channels:
                return func(self, address, *args)

        return wrapper

    @staticmethod
    def get_v_r_s(sig):
        """Converts the signature to a format of 3 numbers v,r,s that are accepted by ethereum"""
        return web3.Web3.toInt(sig[-1]) + 27, web3.Web3.toHex(sig[:32]), web3.Web3.toHex(sig[32:64])

    @check_channel_address
    def send(self, contract_address, amount_in_wei, other_node):
        """
        Sends money to the other address in the channel, and notifies the other node (calling its recieve()).
        :param contract_address: the channel address
        :param amount_in_wei: the amount to send to the other account
        :param other_node: the other account node
        """
        channel_state = self._channels[contract_address]
        last_message_state = channel_state.message_state
        channel_data = channel_state.channel_data
        im_owner1 = channel_data.owner1 == self._account_address
        # owner2 could not send money until he gets some money
        if not im_owner1 and last_message_state is None:
            return
        other_new_balance = amount_in_wei
        serial = STARTING_SERIAL
        if last_message_state is not None:
            serial = last_message_state.serial + 1
            other_new_balance = channel_data.total_wei - (last_message_state.balance - amount_in_wei)
        if other_new_balance < 0 or other_new_balance > channel_data.total_wei or amount_in_wei < 0:
            return

        sign_hex = self._sign(other_new_balance, serial, contract_address)
        new_message_state = MessageState(other_new_balance, serial, sign_hex, contract_address)
        returned_message_state = other_node.receive(new_message_state)
        other_account = channel_data.owner2 if im_owner1 else channel_data.owner1
        my_new_balance = channel_data.total_wei - other_new_balance

        # check if the other sign on the message is exists and valid.
        if returned_message_state is None or not \
                self._check_message_state_sig(my_new_balance, serial, contract_address,
                                              returned_message_state.sig, other_account):
            return
        self._channels[contract_address].message_state = returned_message_state

    def _sign(self, balance, serial, contract_address):
        """Sign on balance, serial number and channel address using the private key"""
        message_hash = web3.Web3.soliditySha3(SIG_TYPES, [balance, serial, contract_address])
        return w3.eth.sign(self._account_address, message_hash)

    @staticmethod
    def _check_message_state_sig(balance, serial, channel_address, sig, pub_key):
        """check that the sign on the balance, serial and channel address using pub_key is valid"""
        return LightningNode._check_sig([balance, serial, channel_address], SIG_TYPES, sig, pub_key)

    @staticmethod
    def _check_sig(message, message_types, sig, signer_pub_key):
        """Check if sign on message is valid"""
        h1 = web3.Web3.soliditySha3(message_types, message)
        message_hash = eth_account.messages.defunct_hash_message(h1)
        return w3.eth.account.recoverHash(message_hash, signature=sig) == signer_pub_key

    def receive(self, state_msg):
        """
        A function that is called when you've received funds.
        You are sent the message about the new channel state that is signed by the other user
        :param state_msg: the sign state from the other account
        :return: a state message with the signature of this node acknowledging the transfer.
        """
        return self._receive(state_msg.channel_address, state_msg)

    @check_channel_address
    def _receive(self, contract_address, state_msg):
        """Implement receive method"""
        channel_state = self._channels[contract_address]
        channel_data = channel_state.channel_data
        message_state = channel_state.message_state
        im_owner1 = channel_state.channel_data.owner1 == self._account_address
        is_sign_ok = LightningNode._check_message_state_sig(state_msg.balance, state_msg.serial,
                                                            contract_address, state_msg.sig,
                                                            channel_data.owner2 if im_owner1 else
                                                            channel_data.owner1)

        other_balance = channel_state.channel_data.total_wei - state_msg.balance
        # check for correct message from other
        if not is_sign_ok or other_balance < 0 or other_balance > channel_data.total_wei:
            return None
        # check that the other not trying to steal from me
        if (message_state is not None and
            (message_state.balance > state_msg.balance or message_state.serial >= state_msg.serial)) or \
                message_state is None and im_owner1:
            return None

        sign_hex = self._sign(other_balance, state_msg.serial, contract_address)
        new_message_state = MessageState(other_balance, state_msg.serial, sign_hex, contract_address)
        self._channels[contract_address].message_state = state_msg
        return new_message_state

    @check_channel_address
    def unilateral_close_channel(self, contract_address, channel_state=None):
        """
        Closes the channel at the given contract address.
        :param contract_address: channel address
        :param channel_state: this is the latest state which is signed by the other node, or None,
        if the channel is to be closed using its current balance allocation.
        """
        channel_state_to_use = self._channels[contract_address] if channel_state is None else channel_state
        message_state = channel_state_to_use.message_state

        # close channel using default split if the message state is None
        if message_state is None:
            tx_hash = channel_state_to_use.channel_data.channel_obj.functions.default_split().transact(self._txn_dict)
        else:
            v, r, s = LightningNode.get_v_r_s(message_state.sig)
            tx_hash = channel_state_to_use.channel_data.channel_obj.functions\
                .one_sided_close(message_state.balance, message_state.serial, v, r, s).transact(self._txn_dict)

        w3.eth.waitForTransactionReceipt(tx_hash)

    @check_channel_address
    def get_current_signed_channel_state(self, chan_contract_address):
        """
        Gets the state of the channel (i.e., the last signed message from the other party)
        :param chan_contract_address: channel address
        :return:
        """
        return self._channels[chan_contract_address]

    @check_channel_address
    def appeal_closed_chan(self, contract_address):
        """
        Checks if the channel at the given address needs to be appealed. If so, an appeal is sent to the
        blockchain.
        :param contract_address: channel address
        :return:
        """
        channel_state = self._channels[contract_address]
        message_state = channel_state.message_state
        # appeal only if current message exists and valid for appeal
        if not message_state or not \
                channel_state.channel_data.channel_obj.functions.is_appeal_valid(channel_state.message_state.serial).call():
            return

        v, r, s = LightningNode.get_v_r_s(message_state.sig)
        tx_hash = channel_state.channel_data.channel_obj.functions.appeal_closure(message_state.balance,
                                                           message_state.serial, v, r, s).transact(self._txn_dict)
        w3.eth.waitForTransactionReceipt(tx_hash)

    @check_channel_address
    def withdraw_funds(self, contract_address):
        """
        Allows the user to withdraw funds from the contract into his address.
        :param contract_address: channel address
        """
        tx_hash = self._channels[contract_address].channel_data.channel_obj.functions.withdraw_funds(
                                                            self._account_address).transact(self._txn_dict)
        w3.eth.waitForTransactionReceipt(tx_hash)

    @check_channel_address
    def debug(self, contract_address):
        """
        A useful debugging method. prints the values of all variables in the contract. (public variables have auto-generated getters).
        :param contract_address: channel address
        """
        channel_state = self._channels[contract_address]
        message_state = channel_state.message_state
        channel_data = channel_state.channel_data
        owner1 = channel_data.owner1
        owner2 = channel_data.owner2
        channel_obj = channel_data.channel_obj
        total_wei = channel_data.total_wei
        balance = message_state.balance
        serial = message_state.serial
        sig = message_state.sig
        print(f"channel state: channel data=(owner1={owner1}, owner2={owner2}, channel_obj={channel_obj}, "
              f"total_wei={total_wei}), message state=(balance={balance}, serial={serial}, sig={sig})")


def wait_k_blocks(k: int, sleep_interval: int = 2):
    start = w3.eth.blockNumber
    time.sleep(sleep_interval)
    while w3.eth.blockNumber < start + k:
        time.sleep(sleep_interval)


def init_scenario():
    print("Creating nodes")
    alice = LightningNode(w3.eth.accounts[0])
    bob = LightningNode(w3.eth.accounts[1])
    print("Creating channel")
    chan_address = alice.establish_channel(bob.get_address(), 10 * 10 ** 18)  # creates a channel between Alice and Bob.
    print("Notifying bob of channel")
    bob.notify_of_channel(chan_address)

    print("channel created", chan_address)
    return alice, bob, chan_address


# Opening and closing channel without sending any money.
def scenario1():
    alice, bob, chan_address = init_scenario()

    print("channel created", chan_address)

    print("ALICE CLOSING UNILATERALLY")
    alice.unilateral_close_channel(chan_address)

    print("waiting")
    wait_k_blocks(APPEAL_PERIOD)

    print("Bob Withdraws")
    bob.withdraw_funds(chan_address)
    print("Alice Withdraws")
    alice.withdraw_funds(chan_address)

# sending money back and forth and then closing with latest state.
def scenario2():
    alice, bob, chan_address = init_scenario()

    print("Alice sends money")
    alice.send(chan_address, 2 * 10**18, bob)
    print("Bob sends some money")
    bob.send(chan_address, 1 * 10**18, alice)
    print("Alice sends money twice!")
    alice.send(chan_address, 2 * 10**18, bob)
    alice.send(chan_address, 2 * 10**18, bob)

    print("BOB CLOSING UNILATERALLY")
    bob.unilateral_close_channel(chan_address)

    print("waiting")
    wait_k_blocks(APPEAL_PERIOD)

    print("Bob Withdraws")
    bob.withdraw_funds(chan_address)
    print("Alice Withdraws")
    alice.withdraw_funds(chan_address)

# sending money, alice tries to cheat, bob appeals.
def scenario3():
    alice, bob, chan_address = init_scenario()

    print("Alice sends money thrice")

    alice.send(chan_address, 1 * 10**18, bob)
    old_state = alice.get_current_signed_channel_state(chan_address)
    alice.send(chan_address, 1 * 10**18, bob)
    alice.send(chan_address, 1 * 10**18, bob)

    print("ALICE TRIES TO CHEAT")
    alice.unilateral_close_channel(chan_address,old_state)

    print("Waiting one blocks")
    wait_k_blocks(1)

    print("Bob checks if he needs to appeal, and appeals if he does")
    bob.appeal_closed_chan(chan_address)

    print("waiting")
    wait_k_blocks(APPEAL_PERIOD)

    print("Bob Withdraws")
    bob.withdraw_funds(chan_address)
    print("Alice Withdraws")
    alice.withdraw_funds(chan_address)

def scenario4():
    alice, bob, chan_address = init_scenario()

    alice.send(chan_address, 2 * 10**18, bob)
    bob.send(chan_address, 2 * 10**18, alice)
    # alice.send(chan_address, 2 * 10**18, bob)
    # alice.send(chan_address, 1 * 10**18, bob)

    print("Alice close channel")
    alice.unilateral_close_channel(chan_address)

    current_state = alice.get_current_signed_channel_state(chan_address)
    local_balance = current_state.message_state.balance
    alice_balance = current_state.channel_data.channel_obj.functions.get_owner1_balance().call()

    print(f"alice balance from contract is: {alice_balance}, local: {local_balance}")
    assert(alice_balance == local_balance)
    # assert((7 * 10**18) == alice_balance)

    print("waiting")
    wait_k_blocks(APPEAL_PERIOD)

    print("Bob Withdraws")
    bob.withdraw_funds(chan_address)
    print("Alice Withdraws")
    alice.withdraw_funds(chan_address)

def scenario5():
    alice, bob, chan_address = init_scenario()
    alice.send(chan_address, 11 * 10**18, bob)
    alice.send(chan_address, -1 * 10**18, bob)
    current_state = alice.get_current_signed_channel_state(chan_address)
    assert(current_state.message_state is None)

    print("Alice close channel")
    alice.unilateral_close_channel(chan_address)

    alice_balance = current_state.channel_data.channel_obj.functions.get_owner1_balance().call()

    print(f"alice balance from contract is: {alice_balance}")
    assert(alice_balance == current_state.channel_data.total_wei)
    assert((10 * 10**18) == alice_balance)

    print("waiting")
    wait_k_blocks(APPEAL_PERIOD)

    print("Bob Withdraws")
    bob.withdraw_funds(chan_address)
    print("Alice Withdraws")
    alice.withdraw_funds(chan_address)


# simple_scenerio()
# scenario1()
# scenario2()
# scenario3()
scenario4()
# scenario5()