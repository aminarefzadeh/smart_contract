from io import StringIO
import binascii

from manticore.ethereum import ABI


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

    @staticmethod
    def print_diff(contract_account, mutant_account, stream):
        for field in ['address', 'name', 'balance', 'storage']:
            stream.write(f'Acount {field}: {getattr(contract_account, field)}\n')
            if getattr(contract_account, field) != getattr(mutant_account, field):
                stream.write(f'* Mutant {field}: {getattr(mutant_account, field)}\n')


class TransactionState:
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


class BlockChianState:
    def __init__(self, transaction_state):
        self.accounts = {}
        self.transaction_state = transaction_state

    def add_account(self, account):
        self.accounts[account.address] = account

    def __eq__(self, other):
        return self.accounts == other.accounts and self.transaction_state == other.transaction_state

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
                BlockChianState.print_accounts_diff(contract_state.accounts, mutant_state.accounts, stream)
        else:
            stream.write('Status: passed\n')


    @staticmethod
    def print_accounts_diff(contract_accounts, mutant_accounts, stream):
        for address in contract_accounts:
            if contract_accounts[address] != mutant_accounts[address]:
                stream.write('-------------\n')
                AccountState.print_diff(contract_accounts[address], mutant_accounts[address], stream)


def make_transaction_human_readable(conc_tx, mevm, state, stream):
    metadata = mevm.get_metadata(conc_tx.address)
    if conc_tx.sort == "CREATE":
        if metadata is not None:
            conc_args_data = conc_tx.data[len(metadata._init_bytecode):]
            arguments = ABI.deserialize(metadata.get_constructor_arguments(), conc_args_data)

            # TODO confirm: arguments should all be concrete?

            stream.write("Constructor(")
            stream.write(
                ",".join(map(repr, map(state.solve_one, arguments)))
            )  # is this redundant since arguments are all concrete?
            stream.write(") -> %s \n" % (conc_tx.result))

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
            if conc_tx.result == "RETURN":
                ret_types = metadata.get_func_return_types(function_id)
                return_data = conc_tx.return_data
                return_values = ABI.deserialize(ret_types, return_data)  # function return

            stream.write("%s(" % function_name)
            stream.write(",".join(map(repr, arguments)))
            stream.write(") -> %s\n" % (conc_tx.result))

            if return_data is not None:
                if len(return_values) == 1:
                    return_values = return_values[0]

                stream.write("return: %r %s\n" % (return_values))
