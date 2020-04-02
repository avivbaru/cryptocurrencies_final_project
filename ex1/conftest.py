import pytest
from ex1 import Wallet, Bank

@pytest.fixture
def bank():
    return Bank()

@pytest.fixture
def bank2():
    return Bank()


@pytest.fixture
def alice():
    return Wallet()


@pytest.fixture
def alice_coin(bank, alice):
    bank.create_money(alice.get_address())
    bank.end_day()
    alice.update(bank)
    return bank.get_utxo()[0]


@pytest.fixture
def bob():
    return Wallet()


@pytest.fixture
def charlie():
    return Wallet()

