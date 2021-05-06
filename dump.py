from state import BlockChianState, AccountState, TransactionState
from manticore.platforms.evm import consts
from manticore.core.smtlib import SelectedSolver
import logging

logger = logging.getLogger(__name__)


def get_evm_state(mevm):
    # print('busy: ', mevm.count_busy_states())
    # print('killed: ', mevm.count_killed_states())
    # print('ready: ', mevm.count_ready_states())
    # print('terminated: ', mevm.count_terminated_states())
    assert len(list(mevm.all_states)) == 1
    state = list(mevm.all_states)[0]
    if not mevm.fix_unsound_symbolication(state):
        print("Not sound")

    transaction_state = TransactionState(len(state.platform.human_transactions), state.platform.last_transaction)
    blockchain = state.platform
    blockchain_state = BlockChianState(transaction_state)

    # Accounts summary
    assert state.can_be_true(True)
    is_something_symbolic = False
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
                # make a free symbolic idex that could address any storage slot
                index = temp_cs.new_bitvec(256)
                # get the storage for account_address
                storage = blockchain.get_storage(account_address)
                # we are interested only in used slots
                # temp_cs.add(storage.get(index) != 0)
                temp_cs.add(storage.is_known(index))
                # Query the solver to get all storage indexes with used slots
                all_used_indexes = SelectedSolver.instance().get_all_values(temp_cs, index)

            if all_used_indexes:
                for i in all_used_indexes:
                    value = storage.get(i)
                    ss[state.solve_one(i, constrain=True)] = state.solve_one(value, constrain=True)

        blockchain_state.add_account(AccountState(account_address, balance, ss, mevm.account_name(account_address)))
    return blockchain_state

