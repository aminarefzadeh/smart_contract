import os
from contextlib import contextmanager
from time import time

from manticore.ethereum import ManticoreEVM

from state import BlockChainState
from utils import solidity_create_contract_with_zero_price, get_argument_from_create_transaction
import shutil
from manticore.utils import config
from manticore.ethereum.plugins import (
    LoopDepthLimiter,
    KeepOnlyIfStorageChanges,
    SkipRevertBasicBlocks,
)


consts = config.get_group("cli")
consts.add(
    "explore_balance",
    default=False,
    description="Explore states in which only the balance was changed",
)

consts.add(
    "skip_reverts",
    default=False,
    description="Simply avoid exploring basic blocks that end in a REVERT",
)


manticore_run_time = 0
project_run_time = 0


def clean_dir():
    mcore_dirs = [item for item in os.listdir('.') if item.startswith('mcore')]
    for mcore_dir in mcore_dirs:
        shutil.rmtree(mcore_dir)


class Analyzer:
    def __init__(self, args):
        self._args = args
        self._main_evm = None
        self._test_cases = []
        self._killed_mutants = []
        self._all_mutants = []
        self._all_test_cases = []

    def _find_test_cases(self):
        print('Finding test cases ...')
        self._main_evm = ManticoreEVM(workspace_url=self._args.workspace)

        if not self._args.thorough_mode:
            self._args.avoid_constant = True
            self._args.exclude_all = True
            self._args.only_alive_testcases = True
            consts_evm = config.get_group("evm")
            consts_evm.oog = "ignore"
            consts.skip_reverts = True

        if consts.skip_reverts:
            self._main_evm.register_plugin(SkipRevertBasicBlocks())

        if consts.explore_balance:
            self._main_evm.register_plugin(KeepOnlyIfStorageChanges())

        if self._args.limit_loops:
            self._main_evm.register_plugin(LoopDepthLimiter())

        with self._main_evm.kill_timeout():
            self._main_evm.multi_tx_analysis(
                self._args.argv[0],
                contract_name=self._args.contract,
                tx_limit=self._args.txlimit,
                tx_use_coverage=not self._args.txnocoverage,
                tx_send_ether=not self._args.txnoether,
                tx_account=self._args.txaccount,
                tx_preconstrain=self._args.txpreconstrain,
                compile_args=vars(self._args),
            )

        self._test_cases = list(self._main_evm.all_states)

    def _concretizing_transactions(self, test_case):
        print('Concretizing symbolic values ...')
        conc_txs = []
        blockchain = test_case.platform
        self._main_evm.fix_unsound_symbolication(test_case)
        human_transactions = list(blockchain.human_transactions)
        for sym_tx in human_transactions:
            conc_tx = sym_tx.concretize(test_case)
            conc_txs.append(conc_tx)
        return conc_txs

    def _find_mutants(self):
        self._all_mutants = os.listdir(self._args.argv[1])

    def _run_test_case_on_mutant(self, mutant_name, test_case, conc_txs):
        print(f'Run test case on {mutant_name}')
        mutant_mevm = self._run_test_case_on_contract(os.path.join(self._args.argv[1], mutant_name), conc_txs)
        mutant_blockchain_state = BlockChainState.create_from_evm(mutant_mevm)
        # terminate
        mutant_mevm.kill()
        mutant_mevm.remove_all()
        return mutant_blockchain_state

    def _run_single_test_case(self, test_case_number):
        with record_project_time():
            test_case = self._test_cases[test_case_number]
            print(f'Start processing test case {test_case_number + 1}')
            not_killed_mutants = list(set(self._all_mutants) - set(self._killed_mutants))

        with record_manticore_time():
            conc_txs = self._concretizing_transactions(test_case)

        with record_project_time():
            mevm = self._run_test_case_on_contract(self._args.argv[0], conc_txs)
            main_blockchain_state = BlockChainState.create_from_evm(mevm)
            self._all_test_cases.append((main_blockchain_state, False))

            is_selected = False
            for mutant_name in not_killed_mutants:
                mutant_blockchain_state = self._run_test_case_on_mutant(mutant_name, test_case, conc_txs)

                if mutant_blockchain_state != main_blockchain_state:
                    print(f'Killed: {mutant_name}')
                    self._killed_mutants.append(mutant_name)
                    is_selected = True

            if is_selected:
                self._all_test_cases[-1] = (main_blockchain_state, True)

            mevm.kill()
            mevm.remove_all()

    def _run_test_cases(self):
        print(f'Start processing {len(self._test_cases)} test cases ...')
        for test_case_number in range(len(self._test_cases)):
            try:
                self._run_single_test_case(test_case_number)
            except Exception as e:
                print(e)
                print('exception on running test case. continuing ...')

    def run(self):
        try:
            with record_project_time():
                self._find_mutants()
            with record_manticore_time():
                self._find_test_cases()

            self._run_test_cases()
            self._print_result()
            if not self._args.no_testcases:
                self._main_evm.finalize(only_alive_states=self._args.only_alive_testcases)
            else:
                self._main_evm.kill()
            for plugin in list(self._main_evm.plugins):
                self._main_evm.unregister_plugin(plugin)

            global manticore_run_time, project_run_time
            print('manticore run time: ' + str(manticore_run_time))
            print('project run time: ' + str(project_run_time))
        finally:
            clean_dir()

    def _print_result(self):
        print('Write result in result.txt')
        f = open(f'result.txt', 'w')
        f.write('Not killed mutants:\n\n')
        not_killed_mutants = list(set(self._all_mutants) - set(self._killed_mutants))
        for mutant_name in not_killed_mutants:
            f.write(f'{mutant_name}\n')

        f.write('\n')
        f.write('Selected test cases\n\n')

        f2 = open('test_cases.txt', 'w')
        f2.write('All test cases:\n\n')

        for i in range(len(self._all_test_cases)):
            test_case, is_selected = self._all_test_cases[i]
            f2.write(f'------------------------- Test case {i+1} -------------------------\n\n')

            if is_selected:
                f2.write(f'* SELECTED\n\n')
                f.write(f'------------------------- Test case {i+1} -------------------------\n\n')
                f.write(str(test_case.transaction_state))
                f.write('\n\n')

            f2.write(str(test_case.transaction_state))
            f2.write('\n\n')

        f.close()
        f2.close()

        print('')
        print(f'Number of mutants: {len(self._all_mutants)}')
        print(f'Number of killed mutants: {len(self._killed_mutants)}')

    def _run_test_case_on_contract(self, contract_code, conc_txs):
        m2 = ManticoreEVM()
        owner_account = m2.create_account(balance=10 ** 10, name="owner", address=self._main_evm.accounts.get('owner').address)
        attacker_account = m2.create_account(balance=10 ** 10, name="attacker",
                                             address=self._main_evm.accounts.get('attacker').address)
        try:
            call_args = get_argument_from_create_transaction(self._main_evm, conc_txs[0])
            create_value = m2.make_symbolic_value()
            m2.constrain(create_value == conc_txs[0].value)
            contract_account = solidity_create_contract_with_zero_price(
                m2,
                contract_code,
                owner=owner_account,
                args=call_args,
                balance=create_value,
                gas=0,
            )
        except Exception as e:
            return m2

        for conc_tx in conc_txs[1:]:
            try:
                m2.transaction(
                    caller=conc_tx.caller,
                    address=contract_account,
                    value=conc_tx.value,
                    data=conc_tx.data,      # data has all needed metadata like function id ([:4]) and argument passed to function
                    gas=0,
                    price=0
                )
            except Exception as e:
                return m2

        return m2


@contextmanager
def record_project_time():
    start_time = time()
    yield
    global project_run_time
    project_run_time += time() - start_time


@contextmanager
def record_manticore_time():
    start_time = time()
    yield
    global manticore_run_time
    manticore_run_time += time() - start_time