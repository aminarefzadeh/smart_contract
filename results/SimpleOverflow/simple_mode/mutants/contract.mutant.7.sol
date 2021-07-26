contract Overflow {
    uint private sellerBalance=0;

    function add(uint value) public{
revert();

        // possible auditor assert
        assert(sellerBalance >= value);
    }
}