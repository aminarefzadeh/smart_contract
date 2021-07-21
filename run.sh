export PYTHONPATH=$PWD
rm -rf ./input/mutants || true
mkdir ./input/mutants
python3 universalmutator/genmutants.py input/contract.sol --mutantDir ./input/mutants
python -u script.py input/contract.sol input/mutants --workspace manticore_results
