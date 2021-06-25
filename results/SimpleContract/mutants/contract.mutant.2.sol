contract SimpleContract {
    uint private sellerBalance=(10+1);

    constructor(uint value, uint value2) public
    {
        assert(value == value2);
        sellerBalance = value;
    }

    function check(uint value) public{
        assert(sellerBalance == value);
    }
}