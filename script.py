from manticore.ethereum import ManticoreEVM
m = ManticoreEVM()
m.multi_tx_analysis('contract.sol')
states = list(m.all_states)

conc_values = {}
for state in states:
    conc_values[state] = []
    blockchain = state.platform
    human_transactions = list(blockchain.human_transactions)
    for transaction in human_transactions:
        conc_values[state].append(transaction.concretize(state))


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
        print('raise exception in CREATE')

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
            print('raise exception')

    return m2


def dump_output(mevm):
    from io import StringIO
    state = list(mevm.all_states)[0]
    mevm.fix_unsound_symbolication(state)
    blockchain = state.platform
    stream = StringIO()
    stream.write(str([tx.concretize(state).to_dict(mevm) for tx in blockchain.transactions[1:]])) # first transaction is create and differ in code
    return stream.getvalue()


for state in states:
    print('-----------------------------')
    print(state)
    mevm = run_test_cases('contract.sol', conc_values[state])
    expected_output = dump_output(mevm)

    for mutate in ['mutate.sol']:
        try:
            mevm = run_test_cases(mutate, conc_values[state])
        except:
            pass

        output = dump_output(mevm)

        if output != expected_output:
            print(output)
            print()
            print(expected_output)

# مشکل اینه که دیتا ها یکی نیستن. در واقع هر بار که تابع concretize صدا زده میشه به مقادیر سیمبولیک یه ولیو جدید اختصاص میده.


