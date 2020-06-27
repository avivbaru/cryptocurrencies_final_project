pragma solidity ^0.5.9;

// this is a skeleton file for the channel contract. Feel free to change as you wish. 
contract Channel{

    address payable public owner1;
    address payable public owner2;

    // uint private owner1_balance;
    // uint private owner2_balance;

    uint256 private initial_owner1_balance;
    uint256 private initial_owner2_balance;

    uint256 private initial_balance;

    uint private appeal_period_len;
    uint private last_block_number_to_appeal;

    int private current_serial_num;
    uint private current_owner1_balance;
    uint private current_owner2_balance;

    enum ChannelState {
        NOT_INITIALIZED,
        // INITIALIZED_NOT_ACTIVE,
        ACTIVE,
        APPEAL_PERIOD_STARTED,
        APPEAL_PERIOD_ENDED
    }
    ChannelState private state = ChannelState.NOT_INITIALIZED;

	//Notice how this modifier is used below to restrict access. Create more if you need them!
    modifier onlyOwners{
        require(msg.sender == owner1 || msg.sender == owner2,
            "Only an owner can call this function.");
        _;
    }

    modifier appealTimeEnded{
        require(block.number >= last_block_number_to_appeal,
            "Can call this function only after appeal has ended.");
        _;
    }


    modifier isInitialized{
        require(state != ChannelState.NOT_INITIALIZED,
            "Contract must be initialized to call this function.");
        _;
    }

    modifier isNotInitialized{
        require(state == ChannelState.NOT_INITIALIZED,
            "Contract must be not initialized to call this function.");
        _;
    }

    modifier isActive{
        require(state == ChannelState.ACTIVE,
            "Contract must be initialized and active to call this function.");
        _;
    }

    modifier isAppealPeriod{
        require(block.number < last_block_number_to_appeal,
            "Must be in appeal period to call this function.");
        _;
    }

    modifier hasAppealEnded{
        require(block.number >= last_block_number_to_appeal,
            "Appeal must end to be able to call this function.");
        _;
    }

    constructor(address payable _other_owner, uint _appeal_period_len) payable public{
        require(msg.value > 0);
		owner1 = msg.sender;
		owner2 = _other_owner;
		initial_balance = msg.value;
		initial_owner1_balance = msg.value;
		appeal_period_len = _appeal_period_len;

	    state = ChannelState.ACTIVE;
	}

	function owner2_deposit_money() payable isNotInitialized external{
	    require(owner2 == msg.sender);

	    initial_balance += msg.value;
	    initial_owner2_balance = msg.value;

	    state = ChannelState.ACTIVE;
	} // TODO: see if to enable to activate

    function default_split() onlyOwners isActive external{
        current_owner1_balance = initial_owner1_balance;
        current_owner2_balance = initial_owner2_balance;

        start_appeal_period(-1);
    }

    function start_appeal_period(int serial_num) private{
        current_serial_num = serial_num;
        last_block_number_to_appeal = block.number + appeal_period_len;
        state = ChannelState.APPEAL_PERIOD_STARTED;
    }

    function one_sided_close(uint256 balance, int serial_num, uint8 v, bytes32 r, bytes32 s) onlyOwners isActive external{
        // closes the channel based on a message by one party. starts the appeal period
        address signerPubKey = owner1;
        if (msg.sender == owner1) {
            signerPubKey = owner2;
        }
        require(verifySig(balance, serial_num,v, r, s, signerPubKey), "Signature must be valid.");
        update_balance(balance);
        start_appeal_period(serial_num);
    }

    function update_balance(uint256 balance) private{
        require(initial_balance >= balance);
        if (msg.sender == owner1) {
            current_owner1_balance = balance;
            current_owner2_balance = initial_balance - balance;
        } else {
            current_owner2_balance = balance;
            current_owner1_balance = initial_balance - balance;
        }
    }

    function verifySig(uint256 balance, int256 serial_num, uint8 v, bytes32 r, bytes32 s, address signerPubKey) view public returns (bool){
        // v,r,s are the signature.
        // signerPubKey is the public key of the signer (this is what we validate the signature against)
        // num1, word1, b1 constitute the message to be signed.

        // the message is made shorter by hashing it:
        bytes32 hashMessage = keccak256(abi.encodePacked(balance,serial_num,address(this)));

        //message signatures are prefixed in ethereum.
        bytes32 messageDigest = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", hashMessage));
        //If the signature is valid, ecrecover ought to return the signer's pubkey:
        return ecrecover(messageDigest, v, r, s)==signerPubKey;
    }

    function appeal_closure(uint256 balance, int serial_num, uint8 v, bytes32 r, bytes32 s) onlyOwners isAppealPeriod external{
        // appeals a one_sided_close. should show a newer signature. only useful within the appeal period
        require(serial_num > current_serial_num);  // TODO: see if you can control serial number to start from 0.
        address signerPubKey = owner1;
        if (msg.sender == owner1) {
            signerPubKey = owner2;
        }
        require(verifySig(balance, serial_num, v, r, s, signerPubKey), "Signature must be valid.");
        update_balance(balance);
        current_serial_num = serial_num;
    }

    function withdraw_funds(address payable dest_address) onlyOwners hasAppealEnded external{
        state = ChannelState.APPEAL_PERIOD_ENDED;
        if (msg.sender == owner1 && current_owner1_balance > 0) {
            uint temp_balance = current_owner1_balance;
            current_owner1_balance = 0;
            dest_address.transfer(temp_balance);
        } else if(msg.sender == owner2 && current_owner2_balance > 0) {
            uint temp_balance = current_owner2_balance;
            current_owner2_balance = 0;
            dest_address.transfer(temp_balance);
        }
    }

    function get_owner1_address() onlyOwners external view returns (address){
        return owner1;
    }

    function get_owner1_balance() onlyOwners external view returns (uint256){
        return current_owner1_balance;
    }

    function get_initial_owner2_balance() onlyOwners isInitialized external view returns (uint256){
        return current_owner2_balance;
    }

    function get_current_balance() onlyOwners external view returns (uint256){
        return initial_balance;
    }

    function is_appeal_valid(int serial_num) onlyOwners isAppealPeriod external view returns (bool){
        return serial_num > current_serial_num;
    }

    function () external payable{
        revert();  // we make this contract non-payable. Money can only be added at creation.
    }
}