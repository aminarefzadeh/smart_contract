pragma solidity ^0.4.25;
contract Overflow {
    uint private sellerBalance=10;

    function Overflow(uint value, uint value2) public
    {
        sellerBalance = value;
    }

    function check(uint value) public{
    }
}
