from manticore.ethereum import ManticoreEVM
from dump import get_evm_state
import logging

logger = logging.getLogger(__name__)

m = ManticoreEVM()
m.multi_tx_analysis('contract.sol')
states = list(m.all_states)

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


def run_test_cases(contract_code, conc_txs):
    m2 = ManticoreEVM()
    owner_account = m2.create_account(balance=10 ** 10, name="owner", address=m.accounts.get('owner').address)
    attacker_account = m2.create_account(balance=10 ** 10, name="attacker",
                                         address=m.accounts.get('attacker').address)
    try:
        contract_account = m2.solidity_create_contract(
            contract_code,
            owner=owner_account,
            args=None,
            balance=conc_txs[0].value,
            gas=230000,
        )
    except Exception as e:
        logger.exception('raise exception in CREATE')

    for conc_tx in conc_txs[1:]:
        try:
            m2.transaction(
                caller=attacker_account,
                address=contract_account,
                value=conc_tx.value,
                data=conc_tx.data,      # data has all needed metadata like function id ([:4]) and argument passed to function
                gas=230000
            )
        except Exception as e:
            logger.exception('raise exception')

    return m2


def dump_output(mevm):
    from io import StringIO
    state = list(mevm.all_states)[0]
    if not mevm.fix_unsound_symbolication(state):
        print("Not sound")
    print(state.platform.last_transaction.result if state.platform.last_transaction else "NO STATE RESULT (?)")
    blockchain = state.platform
    evm_stream = StringIO()
    blockchain.dump(evm_stream, state, mevm, '')
    stream = StringIO()
    for sym_tx in blockchain.human_transactions:
        conc_tx = sym_tx.concretize(state)
        sym_tx.dump(stream, state, mevm, conc_tx=conc_tx)
    tx_output = [tx.concretize(state).to_dict(mevm) for tx in blockchain.transactions[1:]]
    return stream.getvalue(), evm_stream.getvalue()


for state in states:
    print('-----------------------------')
    print(state)
    # different in transaction results between expected_output and state is because of NoAliveStates
    # results: REVERT (not possible transaction so reverted), RETURN (Okey), THROW (Exception),
    print(state.platform.last_transaction.result if state.platform.last_transaction else "NO STATE RESULT (?)")
    mevm = run_test_cases('contract.sol', conc_values[state])
    expected_output = get_evm_state(mevm)

    for mutate in ['mutate.sol']:
        try:
            mevm = run_test_cases(mutate, conc_values[state])
        except:
            pass

        output = get_evm_state(mevm)

        if output != expected_output:
            print(output)
            print()
            print(expected_output)

# solving state instead of transactions

# handle contract with constructor argument

# for checking states:
#   1. try use blockchain hash
#   2. maybe because of the different between contract code we can't use blockchain hash at all. so we should write a custome code
