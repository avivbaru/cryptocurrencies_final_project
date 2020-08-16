
from lightning_channel import LightningNode, APPEAL_PERIOD
from blockchain import BLOCKCHAIN_INSTANCE


def init_scenario():
    print("Creating nodes")
    alice = LightningNode(1)
    bob = LightningNode(2)
    print("Creating channel")
    channel = alice.establish_channel(bob, 10)  # creates a channel between Alice
    # and Bob.
    print("Notifying bob of channel")
    # bob.notify_of_channel(channel, 10)

    return alice, bob, channel

def init_complex_scenario():
    print("Creating nodes")
    alice = LightningNode(1)
    bob = LightningNode(2)
    charlie = LightningNode(3)
    channel_alice_to_bob = alice.establish_channel(bob, 10)
    channel_bob_to_charlie = bob.establish_channel(charlie, 5)

    return alice, bob, charlie, channel_alice_to_bob, channel_bob_to_charlie

def scenario1():
    print("\n\nScenario1")
    alice, bob, channel = init_scenario()

    alice.start_htlc(bob, 5, [])
    # alice.send(2, bob, channel_address)
    # bob.send(2, alice, channel_address)
    # bob.send(2, alice, channel_address)
    # print("ALICE CLOSING UNILATERALLY")
    # alice.close_channel(channel_address)
    # bob.appeal_closed_chan(channel_address)
    # print("waiting")
    # blockchain.wait_k_blocks(APPEAL_PERIOD)
    # print("alice balance: {0}, bob balance: {1}".format(alice.get_balance(), bob.get_balance()))
    # print("Bob Withdraws")
    # bob.withdraw_funds(channel_address)
    # print("Alice Withdraws")
    # alice.withdraw_funds(channel_address)
    # print("alice balance: {0}, bob balance: {1}".format(alice.get_balance(), bob.get_balance()))



# sending money back and forth and then closing with latest state.
def scenario2():
    print("\n\nScenario2")
    alice, bob, channel, blockchain = init_scenario()
    channel_address = channel.address

    alice.start_htlc(5, bob, [bob])
    blockchain.wait_k_blocks(5)
    bob.close_channel_htlc(channel_address)
    bob.close_channel(channel_address)
    print("waiting")
    blockchain.wait_k_blocks(APPEAL_PERIOD)
    print("alice balance: {0}, bob balance: {1}".format(alice.get_balance(), bob.get_balance()))
    bob.withdraw_funds(channel_address)
    alice.withdraw_funds(channel_address)
    print("alice balance: {0}, bob balance: {1}".format(alice.get_balance(), bob.get_balance()))


# sending money, alice tries to cheat, bob appeals.
def scenario3():
    print("\n\nScenario3")
    alice, bob, charlie, channel_alice_to_bob, channel_bob_to_charlie = init_complex_scenario()

    alice.start_htlc(charlie, 0.5, [bob, charlie])
    # charlie.close_channel_htlc(channel_bob_to_charlie.address)
    # bob.find_pre_image(channel_bob_to_charlie.address)
    # bob.close_channel_htlc(channel_alice_to_bob.address)
    # BLOCKCHAIN_INSTANCE.wait_k_blocks(APPEAL_PERIOD)
    print("alice balance: {0}, bob balance: {1}, charlie balance: {2}".format(alice._balance, bob._balance,
                                                                          charlie._balance))
    # bob.withdraw_funds(channel_bob_to_charlie.address)
    # charlie.withdraw_funds(channel_bob_to_charlie.address)
    # bob.withdraw_funds(channel_alice_to_bob.address)
    # alice.withdraw_funds(channel_alice_to_bob.address)
    # print("alice balance: {0}, bob balance: {1}, charlie balance: {2}".format(alice._balance, bob._balance,
    #                                                                       charlie._balance))


# # check that alice cannot send invalid amount of wei
# def scenario4():
#     print("\n\nScenario4")
#     alice, bob, chan_address = init_scenario()
#     alice.send(chan_address, 11 * 10**18, bob)
#     alice.send(chan_address, -1 * 10**18, bob)
#     current_state = alice.get_current_signed_channel_state(chan_address)
#     assert(current_state.message_state is None)
#
#     print("Alice close channel")
#     alice.unilateral_close_channel(chan_address)
#
#     alice_balance = current_state.channel_data.channel_obj.functions.get_owner1_balance().call()
#
#     print(f"alice balance from contract is: {alice_balance}")
#     assert(alice_balance == current_state.channel_data.total_wei)
#     assert((10 * 10**18) == alice_balance)
#
#     print("waiting")
#     wait_k_blocks(APPEAL_PERIOD)
#
#     print("Bob Withdraws")
#     bob.withdraw_funds(chan_address)
#     print("Alice Withdraws")
#     alice.withdraw_funds(chan_address)
#
#
# # test check that alice cannot call unilateral_close_channel twice
# def scenario5():
#     print("\n\nScenario5")
#     alice, bob, chan_address = init_scenario()
#     alice.send(chan_address, 1 * 10**18, bob)
#     old_state = alice.get_current_signed_channel_state(chan_address)
#     assert old_state is not None
#     alice.send(chan_address, 4 * 10 ** 18, bob)
#
#     print("Alice close channel")
#     alice.unilateral_close_channel(chan_address)
#
#     #  tries to take money back by calling one_sided_close again:
#     print("Alice is cheating")
#     try:
#         alice.unilateral_close_channel(chan_address, old_state)
#         assert False
#     except Exception as e:
#         print("No cheating today, Alice!")
#
#     current_state = alice.get_current_signed_channel_state(chan_address)
#     alice_balance = current_state.channel_data.channel_obj.functions.get_owner1_balance().call()
#
#     print(f"alice balance from contract is: {alice_balance}")
#     assert (5 * 10**18) == alice_balance
#
#     print("waiting")
#     wait_k_blocks(APPEAL_PERIOD)
#
#     print("Bob Withdraws")
#     bob.withdraw_funds(chan_address)
#     print("Alice Withdraws")
#     alice.withdraw_funds(chan_address)
#
#
# # bob tries to cheat by using a different channel's state
# def scenario6():
#     print("\n\nScenario6")
#     alice, bob, chan_address = init_scenario()
#     alice.send(chan_address, 1 * 10**18, bob)
#     old_state = bob.get_current_signed_channel_state(chan_address)
#     assert old_state is not None
#
#     print("Alice close channel")
#     alice.unilateral_close_channel(chan_address)
#
#     current_state = alice.get_current_signed_channel_state(chan_address)
#     alice_balance = current_state.channel_data.channel_obj.functions.get_owner1_balance().call()
#
#     print(f"alice balance from contract is: {alice_balance}")
#     assert((9 * 10**18) == alice_balance)
#
#     print("waiting")
#     wait_k_blocks(APPEAL_PERIOD)
#
#     print("Bob Withdraws")
#     bob.withdraw_funds(chan_address)
#     print("Alice Withdraws")
#     alice.withdraw_funds(chan_address)
#
#     print("creating second channel")
#     chan_address = alice.establish_channel(bob.get_address(), 10 * 10 ** 18)  # creates a channel between Alice and Bob.
#     print("Notifying bob of second channel")
#     bob.notify_of_channel(chan_address)
#
#     #  tries to take money back by using a state from a different channel.
#     print("Bob is cheating")
#     try:
#         bob.unilateral_close_channel(chan_address, old_state)
#         assert False
#     except Exception as e:
#         print("No cheating today, Bobby!")
#
#     bob.unilateral_close_channel(chan_address)
#
#     current_state = alice.get_current_signed_channel_state(chan_address)
#     alice_balance = current_state.channel_data.channel_obj.functions.get_owner1_balance().call()
#
#     print(f"alice balance from contract is: {alice_balance}")
#     assert((10 * 10**18) == alice_balance)
#
#     print("waiting")
#     wait_k_blocks(APPEAL_PERIOD)
#
#     print("Bob Withdraws")
#     bob.withdraw_funds(chan_address)
#     print("Alice Withdraws")
#     alice.withdraw_funds(chan_address)
#
#
# # bob returns an evil state of message from receive.
# def scenario7():
#     class EvilLightningNode(LightningNode):
#
#         def receive(self, state_msg):
#             sign_message = super(EvilLightningNode, self).receive(state_msg)
#             sign_message.serial = sign_message.serial + 1
#             sign_message.balance = sign_message.balance + 1
#             sign_message.sig = self._sign(sign_message.balance, sign_message.serial, sign_message.channel_address)
#             return sign_message
#     print("\n\nScenario7")
#     print("Creating nodes")
#     alice = LightningNode(w3.eth.accounts[0])
#     bob = EvilLightningNode(w3.eth.accounts[1])
#     print("Creating channel")
#     chan_address = alice.establish_channel(bob.get_address(), 10 * 10 ** 18)  # creates a channel between Alice and Bob.
#     print("Notifying bob of channel")
#     bob.notify_of_channel(chan_address)
#
#     print("channel created", chan_address)
#     alice.send(chan_address, 1 * 10**18, bob)
#     print("Alice close channel")
#     alice.unilateral_close_channel(chan_address)
#
#     current_state = alice.get_current_signed_channel_state(chan_address)
#     alice_balance = current_state.channel_data.channel_obj.functions.get_owner1_balance().call()
#
#     print(f"alice balance from contract is: {alice_balance}")
#     assert((10 * 10**18) == alice_balance)
#
#     print("waiting")
#     wait_k_blocks(APPEAL_PERIOD)
#
#     print("Bob Withdraws")
#     bob.withdraw_funds(chan_address)
#     print("Alice Withdraws")
#     alice.withdraw_funds(chan_address)
#
#
# #  appeals with an invalid serial num to the contract.
# def scenario8():
#     class EvilLightningNode(LightningNode):
#
#         def appeal_closed_chan(self, contract_address):
#             channel_state = self._other_nodes_to_channels[contract_address]
#             message_state = channel_state.message_state
#             v, r, s = LightningNode.get_v_r_s(message_state.sig)
#             tx_hash = channel_state.channel_data.channel_obj.functions.appeal_closure(message_state.balance,
#                                                                                       message_state.serial, v, r,
#                                                                                       s).transact(self._txn_dict)
#             w3.eth.waitForTransactionReceipt(tx_hash)
#     print("\n\nScenario8")
#     print("Creating nodes")
#     alice = LightningNode(w3.eth.accounts[0])
#     bob = EvilLightningNode(w3.eth.accounts[1])
#     print("Creating channel")
#     chan_address = alice.establish_channel(bob.get_address(), 10 * 10 ** 18)  # creates a channel between Alice and Bob.
#     print("Notifying bob of channel")
#     bob.notify_of_channel(chan_address)
#
#     print("channel created", chan_address)
#     alice.send(chan_address, 1 * 10**18, bob)
#     old_state = alice.get_current_signed_channel_state(chan_address)
#     alice.send(chan_address, 1 * 10**18, bob)
#     print("Alice close channel")
#     alice.unilateral_close_channel(chan_address)
#     try:
#         bob.appeal_closed_chan(old_state)
#         assert False
#     except Exception as e:
#         print("You can't cheat us Bob!")


# scenario1()
# scenario2()
scenario3()
# scenario4()
# scenario5()
# scenario6()
# scenario7()
# scenario8()
