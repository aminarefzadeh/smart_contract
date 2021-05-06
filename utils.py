import binascii
import json
import logging
from multiprocessing import Queue, Process
from queue import Empty as EmptyQueue
from typing import Dict, Optional, Union
import io
import pyevmasm as EVMAsm
import random
import tempfile
import time

from crytic_compile import CryticCompile, InvalidCompilation, is_supported

from manticore.core.manticore import ManticoreBase, ManticoreError

from manticore.core.smtlib import (
    ConstraintSet,
    Array,
    ArrayProxy,
    BitVec,
    Operators,
    BoolConstant,
    Expression,
    issymbolic,
    SelectedSolver,
)
from manticore.core.state import AbandonState
from manticore.ethereum.account import EVMContract, EVMAccount, ABI
from manticore.ethereum.detectors import Detector
from manticore.ethereum.solidity import SolidityMetadata
from manticore.ethereum.state import State
from manticore.exceptions import EthereumError, DependencyError, NoAliveStates
from manticore.platforms import evm
from manticore.utils import config
from manticore.utils.deprecated import deprecated
from manticore.utils.enums import Sha3Type
from manticore.utils.helpers import PickleSerializer, printable_bytes
import logging

logger = logging.getLogger(__name__)


def create_contract(self, owner, balance=0, address=None, init=None, name=None, gas=None):
    """ Creates a contract

        :param owner: owner account (will be default caller in any transactions)
        :type owner: int or EVMAccount
        :param balance: balance to be transferred on creation
        :type balance: int or BitVecVariable
        :param int address: the address for the new contract (optional)
        :param str init: initializing evm bytecode and arguments
        :param str name: a unique name for reference
        :param gas: gas budget for the creation/initialization of the contract
        :rtype: EVMAccount
    """
    if not self.count_ready_states():
        raise NoAliveStates

    nonce = self.get_nonce(owner)
    expected_address = evm.EVMWorld.calculate_new_address(int(owner), nonce=nonce)

    if address is None:
        address = expected_address
    elif address != expected_address:
        raise EthereumError(
            "Address was expected to be %x but was given %x" % (expected_address, address)
        )

    # Name check
    if name is None:
        name = self._get_uniq_name("contract")
    if name in self._accounts:
        # Account name already used
        raise EthereumError("Name already used")

    self._transaction("CREATE", owner, balance, address, data=init, gas=gas, price=0)
    # TODO detect failure in the constructor
    if self.count_ready_states():
        self._accounts[name] = EVMContract(
            address=address, manticore=self, default_caller=owner, name=name
        )
        return self.accounts[name]


def solidity_create_contract_with_zero_price(
    self,
    source_code,
    owner,
    name=None,
    contract_name=None,
    libraries=None,
    balance=0,
    address=None,
    args=(),
    gas=None,
    compile_args=None,
):
    """ Creates a solidity contract and library dependencies

        :param source_code: solidity source code
        :type source_code: string (filename, directory, etherscan address) or a file handle
        :param owner: owner account (will be default caller in any transactions)
        :type owner: int or EVMAccount
        :param contract_name: Name of the contract to analyze (optional if there is a single one in the source code)
        :type contract_name: str
        :param balance: balance to be transferred on creation
        :type balance: int or BitVecVariable
        :param address: the address for the new contract (optional)
        :type address: int or EVMAccount
        :param tuple args: constructor arguments
        :param compile_args: crytic compile options #FIXME(https://github.com/crytic/crytic-compile/wiki/Configuration)
        :type compile_args: dict
        :param gas: gas budget for each contract creation needed (may be more than one if several related contracts defined in the solidity source)
        :type gas: int
        :rtype: EVMAccount
    """
    if compile_args is None:
        compile_args = dict()

    if libraries is None:
        deps = {}
    else:
        deps = dict(libraries)

    contract_names = [contract_name]
    while contract_names:
        contract_name_i = contract_names.pop()
        try:
            compile_results = self._compile(
                source_code, contract_name_i, libraries=deps, crytic_compile_args=compile_args
            )
            md = SolidityMetadata(*compile_results)
            if contract_name_i == contract_name:
                constructor_types = md.get_constructor_arguments()

                if constructor_types != "()":
                    if args is None:
                        args = self.make_symbolic_arguments(constructor_types)

                    constructor_data = ABI.serialize(constructor_types, *args)
                else:
                    constructor_data = b""
                # Balance could be symbolic, lets ask the solver
                # Option 1: balance can not be 0 and the function is marked as not payable
                maybe_balance = balance == 0
                self._publish(
                    "will_solve", None, self.constraints, maybe_balance, "can_be_true"
                )
                must_have_balance = SelectedSolver.instance().can_be_true(
                    self.constraints, maybe_balance
                )
                self._publish(
                    "did_solve",
                    None,
                    self.constraints,
                    maybe_balance,
                    "can_be_true",
                    must_have_balance,
                )
                if not must_have_balance:
                    # balance always != 0
                    if not md.constructor_abi["payable"]:
                        raise EthereumError(
                            f"Can't create solidity contract with balance ({balance}) "
                            f"different than 0 because the contract's constructor is not payable."
                        )

                for state in self.ready_states:
                    world = state.platform

                    expr = Operators.UGE(world.get_balance(owner.address), balance)
                    self._publish("will_solve", None, self.constraints, expr, "can_be_true")
                    sufficient = SelectedSolver.instance().can_be_true(self.constraints, expr,)
                    self._publish(
                        "did_solve", None, self.constraints, expr, "can_be_true", sufficient
                    )

                    if not sufficient:
                        raise EthereumError(
                            f"Can't create solidity contract with balance ({balance}) "
                            f"because the owner account ({owner}) has insufficient balance."
                        )

                contract_account = create_contract(
                    self,
                    owner=owner,
                    balance=balance,
                    address=address,
                    init=md._init_bytecode + constructor_data,
                    name=name,
                    gas=gas,
                )
            else:
                contract_account = create_contract(
                    self, owner=owner, init=md._init_bytecode, balance=0, gas=gas
                )
            if contract_account is None:
                return None

            self.metadata[int(contract_account)] = md

            deps[contract_name_i] = int(contract_account)
        except DependencyError as e:
            contract_names.append(contract_name_i)
            for lib_name in e.lib_names:
                if lib_name not in deps:
                    contract_names.append(lib_name)
        except EthereumError as e:
            logger.info(f"Failed to build contract {contract_name_i} {str(e)}")
            self.kill()
            raise

    # If the contract was created successfully in at least 1 state return account
    for state in self.ready_states:
        if state.platform.get_code(int(contract_account)):
            return contract_account

    logger.info("Failed to compile contract %r", contract_names)
