
from final_project.LightningChannel import LightningNode, w3, APPEAL_PERIOD, wait_k_blocks


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
    print("\n\nScenario1")
    alice_initial_balance = w3.eth.getBalance(w3.eth.accounts[0])
    bob_initial_balance = w3.eth.getBalance(w3.eth.accounts[1])

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

    alice_current_balance = w3.eth.getBalance(w3.eth.accounts[0])
    bob_current_balance = w3.eth.getBalance(w3.eth.accounts[1])
    assert bob_initial_balance - ((10 ** 18) * 0.4) <= bob_current_balance <= bob_initial_balance
    assert alice_initial_balance - ((10 ** 18) * 0.4) <= alice_current_balance <= alice_initial_balance
    # to account for gas


# sending money back and forth and then closing with latest state.
def scenario2():
    print("\n\nScenario2")
    alice_initial_balance = w3.eth.getBalance(w3.eth.accounts[0])
    bob_initial_balance = w3.eth.getBalance(w3.eth.accounts[1])

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

    alice_current_balance = w3.eth.getBalance(w3.eth.accounts[0])
    bob_current_balance = w3.eth.getBalance(w3.eth.accounts[1])
    assert bob_initial_balance + ((10 ** 18) * 4.6) <= bob_current_balance <= bob_initial_balance + ((10 ** 18) * 5)
    assert alice_initial_balance - ((10 ** 18) * 5.4) <= alice_current_balance <= alice_initial_balance + ((10 ** 18) * 5)


# sending money, alice tries to cheat, bob appeals.
def scenario3():
    print("\n\nScenario3")
    alice_initial_balance = w3.eth.getBalance(w3.eth.accounts[0])
    bob_initial_balance = w3.eth.getBalance(w3.eth.accounts[1])
    alice, bob, chan_address = init_scenario()

    print("Alice sends money thrice")

    alice.send(chan_address, 1 * 10**18, bob)
    old_state = alice.get_current_signed_channel_state(chan_address)
    alice.send(chan_address, 1 * 10**18, bob)
    alice.send(chan_address, 1 * 10**18, bob)

    print("ALICE TRIES TO CHEAT")
    alice.unilateral_close_channel(chan_address, old_state)

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

    alice_current_balance = w3.eth.getBalance(w3.eth.accounts[0])
    bob_current_balance = w3.eth.getBalance(w3.eth.accounts[1])

    assert bob_initial_balance + ((10 ** 18) * 2.6) <= bob_current_balance <= bob_initial_balance + ((10 ** 18) * 3)
    assert alice_initial_balance - ((10 ** 18) * 3.4) <= alice_current_balance <= alice_initial_balance + ((10 ** 18) * 3)


# check that alice cannot send invalid amount of wei
def scenario4():
    print("\n\nScenario4")
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


# test check that alice cannot call unilateral_close_channel twice
def scenario5():
    print("\n\nScenario5")
    alice, bob, chan_address = init_scenario()
    alice.send(chan_address, 1 * 10**18, bob)
    old_state = alice.get_current_signed_channel_state(chan_address)
    assert old_state is not None
    alice.send(chan_address, 4 * 10 ** 18, bob)

    print("Alice close channel")
    alice.unilateral_close_channel(chan_address)

    #  tries to take money back by calling one_sided_close again:
    print("Alice is cheating")
    try:
        alice.unilateral_close_channel(chan_address, old_state)
        assert False
    except Exception as e:
        print("No cheating today, Alice!")

    current_state = alice.get_current_signed_channel_state(chan_address)
    alice_balance = current_state.channel_data.channel_obj.functions.get_owner1_balance().call()

    print(f"alice balance from contract is: {alice_balance}")
    assert (5 * 10**18) == alice_balance

    print("waiting")
    wait_k_blocks(APPEAL_PERIOD)

    print("Bob Withdraws")
    bob.withdraw_funds(chan_address)
    print("Alice Withdraws")
    alice.withdraw_funds(chan_address)


# bob tries to cheat by using a different channel's state
def scenario6():
    print("\n\nScenario6")
    alice, bob, chan_address = init_scenario()
    alice.send(chan_address, 1 * 10**18, bob)
    old_state = bob.get_current_signed_channel_state(chan_address)
    assert old_state is not None

    print("Alice close channel")
    alice.unilateral_close_channel(chan_address)

    current_state = alice.get_current_signed_channel_state(chan_address)
    alice_balance = current_state.channel_data.channel_obj.functions.get_owner1_balance().call()

    print(f"alice balance from contract is: {alice_balance}")
    assert((9 * 10**18) == alice_balance)

    print("waiting")
    wait_k_blocks(APPEAL_PERIOD)

    print("Bob Withdraws")
    bob.withdraw_funds(chan_address)
    print("Alice Withdraws")
    alice.withdraw_funds(chan_address)

    print("creating second channel")
    chan_address = alice.establish_channel(bob.get_address(), 10 * 10 ** 18)  # creates a channel between Alice and Bob.
    print("Notifying bob of second channel")
    bob.notify_of_channel(chan_address)

    #  tries to take money back by using a state from a different channel.
    print("Bob is cheating")
    try:
        bob.unilateral_close_channel(chan_address, old_state)
        assert False
    except Exception as e:
        print("No cheating today, Bobby!")

    bob.unilateral_close_channel(chan_address)

    current_state = alice.get_current_signed_channel_state(chan_address)
    alice_balance = current_state.channel_data.channel_obj.functions.get_owner1_balance().call()

    print(f"alice balance from contract is: {alice_balance}")
    assert((10 * 10**18) == alice_balance)

    print("waiting")
    wait_k_blocks(APPEAL_PERIOD)

    print("Bob Withdraws")
    bob.withdraw_funds(chan_address)
    print("Alice Withdraws")
    alice.withdraw_funds(chan_address)


# bob returns an evil state of message from receive.
def scenario7():
    class EvilLightningNode(LightningNode):

        def receive(self, state_msg):
            sign_message = super(EvilLightningNode, self).receive(state_msg)
            sign_message.serial = sign_message.serial + 1
            sign_message.balance = sign_message.balance + 1
            sign_message.sig = self._sign(sign_message.balance, sign_message.serial, sign_message.channel_address)
            return sign_message
    print("\n\nScenario7")
    print("Creating nodes")
    alice = LightningNode(w3.eth.accounts[0])
    bob = EvilLightningNode(w3.eth.accounts[1])
    print("Creating channel")
    chan_address = alice.establish_channel(bob.get_address(), 10 * 10 ** 18)  # creates a channel between Alice and Bob.
    print("Notifying bob of channel")
    bob.notify_of_channel(chan_address)

    print("channel created", chan_address)
    alice.send(chan_address, 1 * 10**18, bob)
    print("Alice close channel")
    alice.unilateral_close_channel(chan_address)

    current_state = alice.get_current_signed_channel_state(chan_address)
    alice_balance = current_state.channel_data.channel_obj.functions.get_owner1_balance().call()

    print(f"alice balance from contract is: {alice_balance}")
    assert((10 * 10**18) == alice_balance)

    print("waiting")
    wait_k_blocks(APPEAL_PERIOD)

    print("Bob Withdraws")
    bob.withdraw_funds(chan_address)
    print("Alice Withdraws")
    alice.withdraw_funds(chan_address)


#  appeals with an invalid serial num to the contract.
def scenario8():
    class EvilLightningNode(LightningNode):

        def appeal_closed_chan(self, contract_address):
            channel_state = self._channels[contract_address]
            message_state = channel_state.message_state
            v, r, s = LightningNode.get_v_r_s(message_state.sig)
            tx_hash = channel_state.channel_data.channel_obj.functions.appeal_closure(message_state.balance,
                                                                                      message_state.serial, v, r,
                                                                                      s).transact(self._txn_dict)
            w3.eth.waitForTransactionReceipt(tx_hash)
    print("\n\nScenario8")
    print("Creating nodes")
    alice = LightningNode(w3.eth.accounts[0])
    bob = EvilLightningNode(w3.eth.accounts[1])
    print("Creating channel")
    chan_address = alice.establish_channel(bob.get_address(), 10 * 10 ** 18)  # creates a channel between Alice and Bob.
    print("Notifying bob of channel")
    bob.notify_of_channel(chan_address)

    print("channel created", chan_address)
    alice.send(chan_address, 1 * 10**18, bob)
    old_state = alice.get_current_signed_channel_state(chan_address)
    alice.send(chan_address, 1 * 10**18, bob)
    print("Alice close channel")
    alice.unilateral_close_channel(chan_address)
    try:
        bob.appeal_closed_chan(old_state)
        assert False
    except Exception as e:
        print("You can't cheat us Bob!")


scenario1()
scenario2()
scenario3()
scenario4()
scenario5()
scenario6()
scenario7()
scenario8()
