

class AccountState:
    def __init__(self, address, balance, storage, name):
        self.address = address
        self.balance = balance
        self.storage = storage
        self.name = name

    def __eq__(self, other):
        return self.address == other.address and self.balance == other.balance and self.storage == other.storage and self.name == other.name

    def __str__(self):
        return f'address: {self.address}\n'\
                f'name: {self.name}\n'\
                f'balance: {self.balance}\n'\
                f'storage: {self.storage}\n'


class TransactionState:
    def __init__(self, transaction_num, last_transaction):
        self.transaction_num = transaction_num
        # different in transaction results between expected_output and state is because of NoAliveStates
        # results: REVERT (not possible transaction so reverted), RETURN (Okey), THROW (Exception),
        self.last_transaction_result = last_transaction.result if last_transaction else "NO STATE RESULT (?)"

    def __eq__(self, other):
        return self.transaction_num == other.transaction_num and self.last_transaction_result == other.last_transaction_result

    def __str__(self):
        return f'{self.transaction_num}: {self.last_transaction_result}\n'


class BlockChianState:
    def __init__(self, transaction_state):
        self.accounts = {}
        self.transaction_state = transaction_state

    def add_account(self, account):
        self.accounts[account.address] = account

    def __eq__(self, other):
        return self.accounts == other.accounts and self.transaction_state == other.transaction_state

    def __str__(self):
        output = ''
        output += str(self.transaction_state)
        for item in self.accounts.values():
            output += str(item)
        return output
