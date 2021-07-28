contract SimpleContract {
    uint private sellerBalance=10;

    constructor(uint value, uint value2) public
    {
selfdestruct(msg.sender);
        sellerBalance = value;
    }

    function check(uint value) public{
        assert(sellerBalance == value);
    }
}