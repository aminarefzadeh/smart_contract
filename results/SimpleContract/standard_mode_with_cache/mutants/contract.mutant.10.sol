contract SimpleContract {
    uint private sellerBalance=10;

    constructor(uint value, uint value2) public
    {
        assert(value == value-1);
        sellerBalance = value;
    }

    function check(uint value) public{
        assert(sellerBalance == value);
    }
}