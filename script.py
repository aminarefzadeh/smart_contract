# from manticore.ethereum import ManticoreEVM
#
# m = ManticoreEVM()
# m2 = ManticoreEVM()
#
#
# m.multi_tx_analysis('contract.sol')
#
# # create account in m2 evm (value from multi_tx_analysis function)
# owner_account = m2.create_account(balance=10 ** 10, name="owner", address=m.accounts.get('owner').address)
# attacker_account = m2.create_account(balance=10 ** 10, name="attacker", address=m.accounts.get('attacker').address)
#
# states = list(m.all_states)
# for state in states:
#     blockchain = state.platform
#
#     human_transactions = list(blockchain.human_transactions)
#
#
#     creating_contract = human_transactions.pop(0)
#     conc_tx = creating_contract.concretize(state)
#
#     # (values from multi_tx_analysis function)
#     contract_account = m2.solidity_create_contract(
#         'mutate.sol',
#         owner=owner_account,
#         args=None,
#         balance=conc_tx.value,
#         gas=230000,
#     )
#
#     for symbolic_tx in human_transactions:
#         conc_tx = symbolic_tx.concretize(state)
#
#         m2.transaction(
#             caller=attacker_account,
#             address=contract_account,
#             value=conc_tx.value,
#             data=conc_tx.data,      # data has all needed metadata like function id ([:4]) and argument passed to function
#             gas=230000
#         )
#
############ version 2


from manticore.ethereum import ManticoreEVM

m = ManticoreEVM()


m.multi_tx_analysis('contract.sol')

states = list(m.all_states)
for state in states:

    for mutate in ['mutate.sol']:

        m2 = ManticoreEVM()
        # create account in m2 evm (value from multi_tx_analysis function)
        owner_account = m2.create_account(balance=10 ** 10, name="owner", address=m.accounts.get('owner').address)
        attacker_account = m2.create_account(balance=10 ** 10, name="attacker",
                                             address=m.accounts.get('attacker').address)

        blockchain = state.platform
        human_transactions = list(blockchain.human_transactions)
        creating_contract = human_transactions.pop(0)
        conc_tx = creating_contract.concretize(state)

        create_value = m2.make_symbolic_value()
        # first add your constrain then use the symbolic value
        # because some contract has no payable function
        m2.constrain(create_value == conc_tx.value)
        contract_account = m2.solidity_create_contract(
            mutate,
            owner=owner_account,
            args=None,
            balance=create_value,
            gas=230000,
        )

        for symbolic_tx in human_transactions:
            conc_tx = symbolic_tx.concretize(state)

            try:
                m2.transaction(
                    caller=attacker_account,
                    address=contract_account,
                    value=conc_tx.value,
                    data=conc_tx.data,      # data has all needed metadata like function id ([:4]) and argument passed to function
                    gas=230000
                )
            except Exception as e:
                print('moshkel dasht', e)
                break
                # what should we do?

        m2_state = list(m2.all_states)[0]
        m2_blockchain = m2_state.platform

        print('okey bood', blockchain.block_hash(), blockchain.block_number(), m2_blockchain.block_hash(), m2_blockchain.block_number())

        m2.finalize()

m.finalize()
# مشکل اینه که دیتا ها یکی نیستن. در واقع هر بار که تابع concretize صدا زده میشه به مقادیر سیمبولیک یه ولیو جدید اختصاص میده.