export PYTHONPATH=$PWD
rm -rf ./input/mutants || true
rm -rf ./manticore_results || true
mkdir ./input/mutants
echo $(date +"%s")
python3 universalmutator/genmutants.py input/contract.sol --mutantDir ./input/mutants
echo $(date +"%s")
python -u script.py input/contract.sol input/mutants --workspace manticore_results
echo $(date +"%s")