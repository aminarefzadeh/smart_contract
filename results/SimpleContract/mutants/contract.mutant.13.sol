contract SimpleContract {
    uint private sellerBalance=10;

    constructor(uint value, uint value2) public
    {
        assert(value == value2);
revert();
    }

    function check(uint value) public{
        assert(sellerBalance == value);
    }
}