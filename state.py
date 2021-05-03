

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



class BlockChianState:
    def __init__(self):
        self.accounts = {}

    def add_account(self, account):
        self.accounts[account.address] = account

    def __eq__(self, other):
        return self.accounts == other.accounts

    def __str__(self):
        output = ''
        for item in self.accounts.values():
            output += str(item)
        return output
