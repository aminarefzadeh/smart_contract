import multiprocessing
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
        self._all_mutants = []
        self._main_contract_results = []
        self._conc_testcases = []

    def _find_test_cases(self):
        print('Finding test cases ...')
        self._main_evm = ManticoreEVM(workspace_url=self._args.workspace)

        if self._args.quick_mode:
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

    def _concretizing_testcases(self):
        for test_case_number in range(len(self._test_cases)):
            test_case = self._test_cases[test_case_number]
            print(f'Concretizing testcase {test_case_number + 1}')
            conc_txs = []
            blockchain = test_case.platform
            self._main_evm.fix_unsound_symbolication(test_case)
            human_transactions = list(blockchain.human_transactions)
            for sym_tx in human_transactions:
                conc_tx = sym_tx.concretize(test_case)
                conc_txs.append(conc_tx)
            self._conc_testcases.append(conc_txs)

    def _find_mutants(self):
        self._all_mutants = sorted(os.listdir(self._args.argv[1]))

    def _run_test_case_on_mutant(self, mutant_name, conc_txs):
        mutant_mevm = self._run_test_case_on_contract(os.path.join(self._args.argv[1], mutant_name), conc_txs)
        mutant_blockchain_state = BlockChainState.create_from_evm(mutant_mevm)
        # terminate
        mutant_mevm.kill()
        mutant_mevm.remove_all()
        return mutant_blockchain_state

    def _run_test_cases_on_main_contract(self):
        for test_case_number in range(len(self._test_cases)):
            print(f'Start running test case {test_case_number + 1} on main contract')
            conc_txs = self._conc_testcases[test_case_number]

            mevm = self._run_test_case_on_contract(self._args.argv[0], conc_txs)
            main_blockchain_state = BlockChainState.create_from_evm(mevm)
            self._main_contract_results.append(main_blockchain_state)
            mevm.kill()
            mevm.remove_all()

    def _run_testcases_on_single_mutant(self, mutant_name, result_dict):
        for test_case_number in range(len(self._test_cases)):
            print(f'Start running test case {test_case_number + 1} on {mutant_name}')
            conc_txs = self._conc_testcases[test_case_number]
            mutant_blockchain_state = self._run_test_case_on_mutant(mutant_name, conc_txs)
            main_blockchain_state = self._main_contract_results[test_case_number]
            if mutant_blockchain_state != main_blockchain_state:
                print(f'Mutant {mutant_name} killed by testcase {test_case_number + 1}')
                result_dict[mutant_name] = test_case_number
                return
            result_dict[mutant_name] = None

    @staticmethod
    def get_mutants_in_batch(all_mutants):
        mutants_num = len(all_mutants)
        number_of_batch = min(int(mutants_num/10), 10)
        mutants_batch = [[] for _ in range(number_of_batch)]
        for i in range(mutants_num):
            mutants_batch[i%number_of_batch].append(all_mutants[i])
        return mutants_batch

    def _run_test_cases_on_mutants(self):
        print(f'Running {len(self._test_cases)} testcases on mutants ...')
        manager = multiprocessing.Manager()
        result_dict = manager.dict()
        mutant_batchs = self.get_mutants_in_batch(self._all_mutants)
        workers = []
        for i in range(len(mutant_batchs)):
            p = multiprocessing.Process(
                target=self._run_test_cases_on_mutants_batch,
                args=(mutant_batchs[i], result_dict)
            )
            workers.append(p)
            p.start()

        for p in workers:
            p.join()

        self._results = result_dict

    def _run_test_cases_on_mutants_batch(self, mutant_list, result_dict):
        for mutant in mutant_list:
            try:
                self._run_testcases_on_single_mutant(mutant, result_dict)
            except Exception as e:
                print(e)
                print('exception on running test case on mutant. continuing ...')

    def run(self):
        try:
            self._find_mutants()

            with record_manticore_time():
                self._find_test_cases()
                self._concretizing_testcases()

            with record_project_time():
                self._run_test_cases_on_main_contract()
                self._run_test_cases_on_mutants()

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
        not_killed_mutants = [
            mutant_name for mutant_name, test_case_number in self._results.items() if test_case_number is None
        ]
        for mutant_name in not_killed_mutants:
            f.write(f'{mutant_name}\n')

        f.write('\n')
        f.write('Selected test cases\n\n')

        f2 = open('test_cases.txt', 'w')
        f2.write('All test cases:\n\n')

        selected_test_case_number = set([
            test_case_number for test_case_number in self._results.values() if test_case_number is not None
        ])

        for test_case_number in range(len(self._test_cases)):
            test_case = self._main_contract_results[test_case_number]
            is_selected = test_case_number in selected_test_case_number

            f2.write(f'------------------------- Test case {test_case_number+1} -------------------------\n\n')

            if is_selected:
                f2.write(f'* SELECTED\n\n')
                f.write(f'------------------------- Test case {test_case_number+1} -------------------------\n\n')
                f.write(str(test_case.transaction_state))
                f.write('\n\n')

            f2.write(str(test_case.transaction_state))
            f2.write('\n\n')

        f.close()
        f2.close()

        print('')
        print(f'Number of mutants: {len(self._all_mutants)}')
        print(f'Number of killed mutants: {len(self._all_mutants) - len(not_killed_mutants)}')

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