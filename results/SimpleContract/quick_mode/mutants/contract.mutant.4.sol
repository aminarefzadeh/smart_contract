contract SimpleContract {
    uint private sellerBalance=10;

    constructor( uint value2,uint value) public
    {
        assert(value == value2);
        sellerBalance = value;
    }

    function check(uint value) public{
        assert(sellerBalance == value);
    }
}