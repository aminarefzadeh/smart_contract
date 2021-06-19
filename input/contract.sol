pragma solidity ^0.4.25;
contract Overflow {
    uint private sellerBalance=10;

    function Overflow(uint value, uint value2) public
    {
        assert(value == value2);
        sellerBalance = value;
    }

    function check(uint value) public{
        assert(sellerBalance == value);
    }
}
