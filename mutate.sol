pragma solidity ^0.4.25;
contract Overflow {
    uint private sellerBalance=0;
    
    function add(uint value) public returns (bool, uint){
        sellerBalance += value; // complicated math with possible overflow

         
    }
}
