import os

from manticore.ethereum import ManticoreEVM
from state import BlockChainState
from utils import solidity_create_contract_with_zero_price, get_argument_from_create_transaction
import logging
import shutil

logger = logging.getLogger(__name__)


def clean_dir():
    mcore_dirs = [item for item in os.listdir('.') if item.startswith('mcore')]
    for mcore_dir in mcore_dirs:
        shutil.rmtree(mcore_dir)


class Analyzer:
    def __init__(self, input_folder='input'):
        self._input_folder = input_folder
        self._main_evm = None
        self._test_cases = []
        self._killed_mutants = []
        self._all_mutants = []
        self._all_test_cases = []

    def _find_test_cases(self):
        print('Finding test cases ...')
        self._main_evm = ManticoreEVM(workspace_url=os.path.join(os.getcwd(), 'manticore_results'))
        self._main_evm.multi_tx_analysis(f'{self._input_folder}/contract.sol')
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
        self._all_mutants = os.listdir(f'{self._input_folder}/mutants')

    def _run_test_case_on_mutant(self, mutant_name, test_case, conc_txs):
        print(f'Run test case on {mutant_name}')
        mutant_mevm = self._run_test_case_on_contract(f'{self._input_folder}/mutants/{mutant_name}', conc_txs)
        mutant_blockchain_state = BlockChainState.create_from_evm(mutant_mevm)
        # terminate
        mutant_mevm.kill()
        mutant_mevm.remove_all()
        return mutant_blockchain_state

    def _run_single_test_case(self, test_case_number):
        test_case = self._test_cases[test_case_number]
        print(f'Start processing test case {test_case_number + 1}')
        not_killed_mutants = list(set(self._all_mutants) - set(self._killed_mutants))

        conc_txs = self._concretizing_transactions(test_case)
        mevm = self._run_test_case_on_contract(f'{self._input_folder}/contract.sol', conc_txs)
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
            except:
                print('exception on running test case. continuing ...')

    def run(self):
        try:
            self._find_mutants()
            self._find_test_cases()
            self._run_test_cases()
            self._print_result()
            self._main_evm.finalize()
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
                    caller=attacker_account,
                    address=contract_account,
                    value=conc_tx.value,
                    data=conc_tx.data,      # data has all needed metadata like function id ([:4]) and argument passed to function
                    gas=0,
                    price=0
                )
            except Exception as e:
                return m2

        return m2


if __name__ == '__main__':
    analyzer = Analyzer()
    analyzer.run()
