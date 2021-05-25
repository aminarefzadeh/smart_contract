import os

from manticore.ethereum import ManticoreEVM
from dump import get_evm_state
from state import BlockChianState
from utils import solidity_create_contract_with_zero_price, get_argument_from_create_transaction
import logging
import shutil

logger = logging.getLogger(__name__)

print('Start analysing contract ...')
m = ManticoreEVM()
m.multi_tx_analysis('contract.sol')
states = list(m.all_states)
print('Finish Analysing')

print('Concretizing symbolic values ...')
conc_values = {}
for state in states:
    from io import StringIO
    conc_values[state] = []
    blockchain = state.platform
    m.fix_unsound_symbolication(state)
    state.platform.dump(StringIO(), state, m, '')
    human_transactions = list(blockchain.human_transactions)
    for sym_tx in human_transactions:
        conc_tx = sym_tx.concretize(state)
        sym_tx.dump(StringIO(), state, m, conc_tx=conc_tx)
        conc_values[state].append(conc_tx)
print('Finish concretizing')


def run_test_cases(contract_code, conc_txs):
    m2 = ManticoreEVM()
    owner_account = m2.create_account(balance=10 ** 10, name="owner", address=m.accounts.get('owner').address)
    attacker_account = m2.create_account(balance=10 ** 10, name="attacker",
                                         address=m.accounts.get('attacker').address)
    try:
        call_args = get_argument_from_create_transaction(m, conc_txs[0])
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
        logger.error('raise exception in CREATE')
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
            logger.exception('raise exception')

    return m2


def save_state_status(state_id, killed_mutant, not_killed_mutant, blockchain_state):
    f = open(f'result/state_{state_id}/summary.txt', 'w')
    f.write(str(blockchain_state))
    f.write('\n')
    f.write('Killed mutant:\n')
    for mutant in killed_mutant:
        f.write(f'{mutant}\n')
    f.write('\nNot killed mutant:\n')
    for mutant in not_killed_mutant:
        f.write(f'{mutant}\n')

    f.write(f'\nScore: {len(killed_mutant)/(len(killed_mutant)+len(not_killed_mutant))*100}%\n')
    f.close()


def save_mutant_diff(state_id, mutant_name, contract_state, mutant_state):
    f = open(f'result/state_{state_id}/{mutant_name}', 'w')
    BlockChianState.print_diff(contract_state, mutant_state, f)
    f.close()


def clean_dir():
    mcore_dirs = [item for item in os.listdir('.') if item.startswith('mcore')]
    for mcore_dir in mcore_dirs:
        shutil.rmtree(mcore_dir)


if os.path.isdir('result'):
    shutil.rmtree('result')

os.mkdir('result')
print(f'Start processing {len(states)} paths ...')
state_id = 1
for state in states:
    print(f'Start processing path {state_id}')
    os.mkdir(f'result/state_{state_id}')
    mevm = run_test_cases('contract.sol', conc_values[state])
    expected_output = get_evm_state(mevm)
    killed_mutant = []
    not_killed_mutant = []
    for mutant in ['mutant.sol']:
        print(f'Run test case on {mutant}')
        mutant_mevm = run_test_cases(mutant, conc_values[state])
        output = get_evm_state(mutant_mevm)

        if output != expected_output:
            killed_mutant.append(mutant)

        else:
            not_killed_mutant.append(mutant)

        save_mutant_diff(state_id, mutant, expected_output, output)
        # terminate
        mutant_mevm.kill()
        mutant_mevm.remove_all()
        print(f'Finish running test case on {mutant}')

    save_state_status(state_id, killed_mutant, not_killed_mutant, expected_output)
    mevm.kill()
    mevm.remove_all()
    print(f'Finish processing path {state_id}')
    state_id += 1
clean_dir()


# solving state instead of transactions

# handle contract with constructor argument

# for checking states:
#   1. last transaction status maybe different but world state is the same ??
#   2. balance problem --> problem is solidity_create_contract>create_contract>_transaction>run
#   becuase you set gas usage like 230000, but according to contract length create contract use different gas amount
#   I correct this, using price=0 for transaction and price=0 in create_account
#   3. don't count gas in word state (transaction without gas usage)
#   4. contract with input argument
