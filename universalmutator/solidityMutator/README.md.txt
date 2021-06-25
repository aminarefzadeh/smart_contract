# **Mutation testing for solidity language**
Universal mutator tool is a tool based purely on regexp-specified rewrite of code lines for mutation generation, including multi-language rules aided by special rules for different languages .
More information about universal mutator can be found on [GitHub](https://github.com/agroce/universalmutator)

This is an extend for universal mutator tool  which has effective rules for solidity language . These rules can  regenerate 10 of 15 famous faulty smart contracts, which have result in millions of dollars loss.
You can read more about the mutation operators which on (address of paper)
Rules are implemented by python regular-expression and can be found in *sol.rules*

# **How To USE IT**
Download the package and go to soliditymutation directory . Then run the following command:
```javascript
python genmutants.py ./example/example.sol solidity sol.rules
```
if you have python compiler installed , it should generate a number of valid mutants and get the number of valid , not valid and redundant mutants .
You can get more information about using it with 
```javascript
python genmutants.py --help 
```


 
