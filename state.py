from io import StringIO
import binascii

from manticore.core.smtlib import issymbolic
from manticore.ethereum import ABI

from utils import get_argument_from_create_transaction


class AccountState:
    """
        Saving accounts state of EVM
        Accounts consist of address, name, balance and storage(for contracts)

        Methods:
            __eq__(self, other) --> checks the equality of accounts state in two different evm (main contract and mutate)
            __str__(self) --> human readable accounts state
            print_diff(contract_account, mutant_account, stream) --> print human readable difference between two accounts state
    """

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

    @staticmethod
    def print_diff(contract_account, mutant_account, stream):
        for field in ['address', 'name', 'balance', 'storage']:
            stream.write(f'Acount {field}: {getattr(contract_account, field)}\n')
            if getattr(contract_account, field) != getattr(mutant_account, field):
                stream.write(f'* Mutant {field}: {getattr(mutant_account, field)}\n')


class TransactionState:
    """
        Saving transactions state of EVM
        Transactions are function calls
        Transactions state consist of type, from_address, from_name, to_address, to_name, value, gas, data,
                                        used_gas, result, depth and return_data

        Methods:
            __eq__(self, other) --> checks the equality of transactions state in two different evm (main contract and mutate)
            __str__(self) --> human readable transactions state
            print_diff(contract_account, mutant_account, stream) --> print human readable difference between two transactions state
            create(transactions, state, mevm): --> creates a transactions state with provided argument
    """

    def __init__(self, result, all_tx_summary):
        self.result = result
        self.all_tx_summary = all_tx_summary

    def __eq__(self, other):
        return self.result == other.result

    def __str__(self):
        return '\n'.join(self.all_tx_summary)

    @staticmethod
    def print_diff(contract, mutant, stream):
        if mutant != contract:
            for i in range(len(contract.result)):
                contract_transaction_result = contract.result[i]
                if i >= len(mutant.result):
                    stream.write('Diff path:\n\n')
                    stream.write('Contract:\n')
                    stream.write(contract_transaction_result)
                    stream.write('* No similar transaction in mutant\n')
                    return
                mutant_transaction_result = mutant.result[i]
                if contract_transaction_result == mutant_transaction_result:
                    if i == 0:
                        stream.write('Similar path:\n\n')
                    stream.write(mutant.all_tx_summary[i])
                    stream.write('\n')
                else:
                    stream.write('\n')
                    stream.write('Diff path:\n\n')
                    stream.write('Contract:\n')
                    stream.write(contract.all_tx_summary[i])
                    stream.write('\n\n')
                    stream.write('Mutant:\n')
                    stream.write(mutant.all_tx_summary[i])
                    TransactionState.print_diff_result(contract_transaction_result, mutant_transaction_result, stream)
                    return
        else:
            stream.write('No difference in transactions\n')

    @staticmethod
    def print_diff_result(contract_result, mutant_result, stream):
        if contract_result['data'] != mutant_result['data']:
            stream.write('* Call arguments are different\n')
        if contract_result['return_data'] != mutant_result['return_data']:
            stream.write('* Return values are different\n')

        for field in ['result', 'type', 'from_address', 'from_name', 'to_address',
                      'to_name', 'value', 'gas', 'used_gas', 'depth']:
            if contract_result[field] != mutant_result[field]:
                stream.write(f'* Contract {field} is {contract_result[field]} '
                             f'but mutant {field} is {mutant_result[field]}\n')

    @staticmethod
    def create(transactions, state, mevm):
        transactions_result = []
        transactions_human_readable = []
        for index in range(len(transactions)):
            sym_tx = transactions[index]
            conc_tx = sym_tx.concretize(state)
            result = dict(
                type=conc_tx.sort,
                from_address=conc_tx.caller,
                from_name=mevm.account_name(conc_tx.caller),
                to_address=conc_tx.address,
                to_name=mevm.account_name(conc_tx.address),
                value=conc_tx.value,
                gas=conc_tx.gas,
                data=binascii.hexlify(conc_tx.data).decode(),
                used_gas=conc_tx.used_gas,
                result=conc_tx.result,
                depth=conc_tx.depth,
                return_data=binascii.hexlify(conc_tx.return_data).decode()
            )
            if index == 0:
                # pop data due to difference in contracts text
                result['data'] = ''
                result['return_data'] = ''
            transactions_result.append(result)
            transaction_summary = StringIO()
            make_transaction_human_readable(conc_tx, mevm, state, transaction_summary)
            transactions_human_readable.append(transaction_summary.getvalue())

        return TransactionState(transactions_result, transactions_human_readable)


class BlockChainState:
    """
        Saving blockchain state of EVM
        Blockchain state consist of transactions state and accounts state

        Methods:
            create_from_evm(mevm): --> create a blockchain state from mevm
            __eq__(self, other) --> checks the equality of blockchain state in two different evm (main contract and mutate)
            __str__(self) --> human readable blackchain state
            print_diff(contract_account, mutant_account, stream) --> print human readable difference between two blockchain state
    """

    def __init__(self, transaction_state, log_state):
        self.accounts = {}
        self.transaction_state = transaction_state
        self.log_state = log_state

    def add_account(self, account):
        self.accounts[account.address] = account

    def __eq__(self, other):
        return self.accounts == other.accounts and \
               self.transaction_state == other.transaction_state and \
               self.log_state == other.log_state

    def __str__(self):
        output = 'Path:\n\n'
        output += str(self.transaction_state)
        output += '\n\n'
        output += 'Accounts: \n\n'
        for item in self.accounts.values():
            output += str(item)
            output += '------------\n'
        return output

    @staticmethod
    def print_diff(contract_state, mutant_state, stream):
        if contract_state != mutant_state:
            stream.write('Status: killed\n')
            if contract_state.transaction_state != mutant_state.transaction_state:
                stream.write('\n')
                TransactionState.print_diff(contract_state.transaction_state, mutant_state.transaction_state, stream)
            if contract_state.accounts != mutant_state.accounts:
                stream.write('\n')
                BlockChainState.print_accounts_diff(contract_state.accounts, mutant_state.accounts, stream)
        else:
            stream.write('Status: passed\n')

    @staticmethod
    def create_from_evm(mevm):
        from state import BlockChainState, AccountState, TransactionState
        from manticore.platforms.evm import consts
        from manticore.core.smtlib import SelectedSolver
        if len(list(mevm.all_states)) == 0:
            empty_transaction_state = TransactionState(result=[], all_tx_summary='')
            return BlockChainState(empty_transaction_state, None)

        state = list(mevm.all_states)[0]
        if not mevm.fix_unsound_symbolication(state):
            print("Not sound")

        transactions = list(state.platform.transactions)
        transaction_state = TransactionState.create(transactions, state, mevm)
        blockchain = state.platform
        blockchain_state = BlockChainState(
            transaction_state,
            BlockChainState.get_log(state, blockchain)
        )

        assert state.can_be_true(True)
        for account_address in blockchain.accounts:
            account_address = state.solve_one(account_address, constrain=True)

            balance = blockchain.get_balance(account_address)
            if not consts.ignore_balance:
                balance = state.solve_one(balance, constrain=True)

            storage = blockchain.get_storage(account_address)
            ss = {}
            concrete_indexes = set()
            for sindex in storage.written:
                concrete_indexes.add(state.solve_one(sindex, constrain=True))

            for index in concrete_indexes:
                ss[index] = state.solve_one(storage[index], constrain=True)

            storage = blockchain.get_storage(account_address)

            if consts.sha3 is consts.sha3.concretize:
                all_used_indexes = []
                with state.constraints as temp_cs:
                    index = temp_cs.new_bitvec(256)
                    storage = blockchain.get_storage(account_address)
                    temp_cs.add(storage.is_known(index))
                    all_used_indexes = SelectedSolver.instance().get_all_values(temp_cs, index)

                if all_used_indexes:
                    for i in all_used_indexes:
                        value = storage.get(i)
                        ss[state.solve_one(i, constrain=True)] = state.solve_one(value, constrain=True)

            blockchain_state.add_account(
                AccountState(account_address, balance, ss, mevm.account_name(account_address)))
        return blockchain_state

    @staticmethod
    def get_log(state, blockchain):
        is_something_symbolic = False
        log_state = []
        for log_item in blockchain.logs:
            is_log_symbolic = issymbolic(log_item.memlog)
            is_something_symbolic = is_log_symbolic or is_something_symbolic
            solved_memlog = state.solve_one(log_item.memlog)

            topics = []
            for i, topic in enumerate(log_item.topics):
                topics.append((i, state.solve_one(topic)))
            log_state.append((log_item.address, binascii.hexlify(solved_memlog).decode(), topics))
        return log_state

    @staticmethod
    def print_accounts_diff(contract_accounts, mutant_accounts, stream):
        for address in contract_accounts:
            if contract_accounts[address] != mutant_accounts[address]:
                stream.write('-------------\n')
                AccountState.print_diff(contract_accounts[address], mutant_accounts[address], stream)


def make_transaction_human_readable(conc_tx, mevm, state, stream):
    metadata = mevm.get_metadata(conc_tx.address)
    if conc_tx.sort == "CREATE":
        stream.write("owner: Constructor(")
        if metadata is not None:
            conc_args_data = conc_tx.data[len(metadata._init_bytecode):]
            arguments = ABI.deserialize(metadata.get_constructor_arguments(), conc_args_data)
            stream.write(
                ",".join(map(repr, map(state.solve_one, arguments)))
            )  # is this redundant since arguments are all concrete?
        stream.write(") with initial balance %s -> %s \n" % (conc_tx.value, conc_tx.result))

    if conc_tx.sort == "CALL":
        if metadata is not None:
            calldata = conc_tx.data

            function_id = bytes(calldata[:4])  # hope there is enough data
            signature = metadata.get_func_signature(function_id)
            function_name = metadata.get_func_name(function_id)
            if signature:
                _, arguments = ABI.deserialize(signature, calldata)
            else:
                arguments = (calldata,)

            return_data = None
            return_values = None
            if conc_tx.result == "RETURN":
                ret_types = metadata.get_func_return_types(function_id)
                return_data = conc_tx.return_data
                return_values = ABI.deserialize(ret_types, return_data)  # function return

            stream.write("%s: %s(" % (mevm.account_name(conc_tx.caller), function_name))
            stream.write(",".join(map(repr, arguments)))
            if conc_tx.value != 0:
                stream.write(") with %d wei -> %s\n" % (conc_tx.value, conc_tx.result))
            else:
                stream.write(") -> %s\n" % (conc_tx.result))

            if return_data is not None:
                if len(return_values) == 1:
                    return_values = return_values[0]
                stream.write(f"return: {return_values}\n")
