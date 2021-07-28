contract Overflow {
    uint private sellerBalance=0;

    function add(uint value) public{
selfdestruct(msg.sender);

        // possible auditor assert
        assert(sellerBalance >= value);
    }
}