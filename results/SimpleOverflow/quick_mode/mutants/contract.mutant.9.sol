contract Overflow {
    uint private sellerBalance=0;

    function add(uint value) public{
        sellerBalance += value; // complicated math with possible overflow

        // possible auditor assert
        assert(sellerBalance == value);
    }
}