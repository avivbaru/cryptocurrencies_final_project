import web3
import time
import eth_account.messages
from contracts_variables import COMPILED_CHANNEL, ABI_CHANNEL
import web3.contract
from web3.contract import Contract
from typing import Dict, AnyStr

w3 = web3.Web3(web3.HTTPProvider("http://127.0.0.1:7545"))
APPEAL_PERIOD = 3  # the appeal period in blocks.
STARTING_SERIAL = 0


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


    def get_address(self):
        """
        Returns the address of this node on the blockchain (its ethereum wallet).
        :return:
        """
        return self._account_address

    def establish_channel(self, other_party_address, amount_in_wei):
        """
        Sets up a channel with another user at the given ethereum address.
        Returns the address of the contract on the blockchain.
        :param other_party_address:
        :param amount_in_wei:
        :return: returns the contract address on the blockchain
        """
        contract_factory = w3.eth.contract(abi=ABI_CHANNEL, bytecode=COMPILED_CHANNEL["object"])

        txn_dict = {'from': self._account_address, 'value': amount_in_wei}
        tx_hash = contract_factory.constructor(other_party_address, APPEAL_PERIOD).transact(txn_dict)

        tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)

        contract = w3.eth.contract(address=tx_receipt.contractAddress, abi=ABI_CHANNEL)
        self._channels[contract.address] = ChannelState(ChannelData(contract, self._account_address,
                                                                    other_party_address, amount_in_wei))
        return contract.address

    def notify_of_channel(self, contract_address):
        """
        A function that is called when someone created a channel with you and wants to let you know.
        :param contract_address:
        :return:
        """
        contract = w3.eth.contract(address=contract_address, abi=ABI_CHANNEL)
        balance = contract.functions.get_current_balance().call()
        owner1 = contract.functions.get_owner1_address().call()
        self._channels[contract_address] = ChannelState(ChannelData(contract, owner1,
                                                                    self._account_address, balance))

    @staticmethod
    def get_v_r_s(sig):
        """Converts the signature to a format of 3 numbers v,r,s that are accepted by ethereum"""
        return web3.Web3.toInt(sig[-1]) + 27, web3.Web3.toHex(sig[:32]), web3.Web3.toHex(sig[32:64])

    def send(self, contract_address, amount_in_wei, other_node):
        """
        Sends money to the other address in the channel, and notifies the other node (calling its recieve()).
        :param contract_address:
        :param amount_in_wei:
        :param other_node:
        :return:
        """
        if contract_address in self._channels:
            channel_state = self._channels[contract_address]
            im_owner1 = channel_state.channel_data.owner1 == self._account_address
            if not im_owner1 and channel_state.message_state is None:
                return
            balance = amount_in_wei if (im_owner1 and channel_state.message_state is None) else \
                channel_state.channel_data.total_wei - (channel_state.message_state.balance - amount_in_wei)
            if balance < 0 or balance > channel_state.channel_data.total_wei:
                return

            serial = channel_state.message_state.serial + 1 if channel_state.message_state is not None else STARTING_SERIAL
            sign_hex = self._sign(balance, serial, contract_address)
            message_state = MessageState(balance, serial, sign_hex, contract_address)
            returned_message_state = other_node.receive(message_state)

            if returned_message_state is not None:
                other_account = channel_state.channel_data.owner2 if im_owner1 else channel_state.channel_data.owner1
                is_sign_ok = self.check_sig_from(returned_message_state, channel_state.channel_data.total_wei -
                                                 balance, other_account)
                if not is_sign_ok:
                    return
                self._channels[contract_address].message_state = returned_message_state

    def _sign(self, balance, serial, contract_address):
        message_hash = web3.Web3.soliditySha3(['uint256', 'int256', 'address'], [balance, serial, contract_address])
        return w3.eth.sign(self._account_address, message_hash)

    def check_sig_from(self, message_state, balance, pub_key):
        return self._check_sig([balance, message_state.serial, message_state.channel_address],
                                ['uint256', 'int256', 'address'], message_state.sig, pub_key)

    def _check_sig(self, message, message_types, sig, signer_pub_key):
        h1 = web3.Web3.soliditySha3(message_types, message)
        message_hash = eth_account.messages.defunct_hash_message(h1)
        return w3.eth.account.recoverHash(message_hash, signature=sig) == signer_pub_key

    def receive(self, state_msg):
        """
        A function that is called when you've received funds.
        You are sent the message about the new channel state that is signed by the other user
        :param state_msg:
        :return: a state message with the signature of this node acknowledging the transfer.
        """
        if state_msg.channel_address in self._channels:
            channel_state = self._channels[state_msg.channel_address]
            im_owner1 = channel_state.channel_data.owner1 == self._account_address
            is_sign_ok = self.check_sig_from(state_msg, state_msg.balance,
                                            channel_state.channel_data.owner2 if im_owner1 else
                                            channel_state.channel_data.owner1)

            new_balance = channel_state.channel_data.total_wei - state_msg.balance
            if not is_sign_ok or new_balance < 0 or new_balance > channel_state.channel_data.total_wei:
                return None
            if channel_state.message_state is not None and (channel_state.message_state.balance > state_msg.balance or
                    channel_state.message_state.serial >= state_msg.serial):
                return None

            sign_hex = self._sign(new_balance, state_msg.serial, state_msg.channel_address)
            message_state = MessageState(new_balance, state_msg.serial, sign_hex, state_msg.channel_address)
            self._channels[state_msg.channel_address].message_state = state_msg
            return message_state

    def unilateral_close_channel(self, contract_address, channel_state=None):
        """
        Closes the channel at the given contract address.
        :param contract_address:
        :param channel_state: this is the latest state which is signed by the other node, or None,
        if the channel is to be closed using its initial balance allocation.
        :return:
        """
        if contract_address in self._channels:
            txn_dict = {'from': self._account_address}
            channel_state = self._channels[contract_address] if channel_state is None else channel_state
            message_state = channel_state.message_state

            if message_state is None:
                tx_hash = channel_state.channel_data.channel_obj.functions.default_split().transact(txn_dict)
            else:
                v, r, s = LightningNode.get_v_r_s(message_state.sig)
                tx_hash = channel_state.channel_data.channel_obj.functions\
                    .one_sided_close(message_state.balance, message_state.serial, v, r, s).transact(txn_dict)

            w3.eth.waitForTransactionReceipt(tx_hash)

    def get_current_signed_channel_state(self, chan_contract_address):
        """
        Gets the state of the channel (i.e., the last signed message from the other party)
        :param chan_contract_address:
        :return:
        """
        if chan_contract_address in self._channels:
            return self._channels[chan_contract_address]
        return None

    def appeal_closed_chan(self, contract_address):
        """
        Chekcs if the channel at the given address needs to be appealed. If so, an appeal is sent to the blockchain.
        :param contract_address:
        :return:
        """
        if contract_address in self._channels and self._channels[contract_address].message_state:
            channel_state = self._channels[contract_address]
            is_appeal_valid = channel_state.channel_data.channel_obj.functions.is_appeal_valid(channel_state.message_state.serial).call()
            if not is_appeal_valid:
                return

            txn_dict = {'from': self._account_address}
            message_state = channel_state.message_state
            v, r, s = LightningNode.get_v_r_s(message_state.sig)
            tx_hash = channel_state.channel_data.channel_obj.functions.appeal_closure(message_state.balance,
                                                               message_state.serial, v, r, s).transact(txn_dict)
            w3.eth.waitForTransactionReceipt(tx_hash)

    def withdraw_funds(self, contract_address):
        """
        Allows the user to withdraw funds from the contract into his address.
        :param contract_address:
        :return:
        """
        if contract_address in self._channels:
            channel_state = self._channels[contract_address]
            txn_dict = {'from': self._account_address}
            tx_hash = channel_state.channel_data.channel_obj.functions.withdraw_funds(self._account_address).transact(txn_dict)
            w3.eth.waitForTransactionReceipt(tx_hash)

    def debug(self, contract_address):
        """
        A useful debugging method. prints the values of all variables in the contract. (public variables have auto-generated getters).
        :param contract_address:
        :return:
        """
        if contract_address in self._channels:
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