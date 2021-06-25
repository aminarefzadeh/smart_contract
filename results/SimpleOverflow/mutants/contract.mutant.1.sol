contract Overflow {
    uint private sellerBalance=0;

    function add( uint,uint value) public returns (bool){
        sellerBalance += value; // complicated math with possible overflow

        // possible auditor assert
        assert(sellerBalance >= value);
    }
}