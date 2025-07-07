// SPDX-License-Identifier: MIT
pragma solidity ^0.8.4;

/**
 * @title Advanced ERC-20 Token Example
 * @dev This contract demonstrates advanced ERC-20 features including:
 * - Standard ERC-20 functionality
 * - Mintable tokens
 * - Burnable tokens
 * - Pausable transfers
 * - Ownership controls
 * - Batch operations
 */

import "./StellarisToken.sol";

contract AdvancedERC20 is StellarisToken {
    // Additional features specific to this token
    uint256 public constant MAX_SUPPLY = 10000000 * 10**18; // 10 million tokens max
    uint256 public mintedSupply;
    
    mapping(address => bool) public minters;
    mapping(address => bool) public blacklisted;
    
    event MinterAdded(address indexed minter);
    event MinterRemoved(address indexed minter);
    event Blacklisted(address indexed account);
    event Unblacklisted(address indexed account);
    
    modifier onlyMinter() {
        require(minters[msg.sender] || msg.sender == owner, "AdvancedERC20: caller is not a minter");
        _;
    }
    
    modifier notBlacklisted(address account) {
        require(!blacklisted[account], "AdvancedERC20: account is blacklisted");
        _;
    }
    
    constructor(
        string memory _name,
        string memory _symbol,
        uint256 _initialSupply
    ) StellarisToken(_name, _symbol, 18, _initialSupply) {
        mintedSupply = _initialSupply * 10**18;
        minters[msg.sender] = true;
        emit MinterAdded(msg.sender);
    }
    
    // Override transfer to add blacklist check
    function transfer(address recipient, uint256 amount) public override notBlacklisted(msg.sender) notBlacklisted(recipient) returns (bool) {
        return super.transfer(recipient, amount);
    }
    
    // Override transferFrom to add blacklist check
    function transferFrom(address sender, address recipient, uint256 amount) public override notBlacklisted(sender) notBlacklisted(recipient) returns (bool) {
        return super.transferFrom(sender, recipient, amount);
    }
    
    // Override mint to add supply cap
    function mint(address to, uint256 amount) public override onlyMinter notBlacklisted(to) {
        require(mintedSupply + amount <= MAX_SUPPLY, "AdvancedERC20: exceeds max supply");
        mintedSupply += amount;
        super.mint(to, amount);
    }
    
    // Minter management
    function addMinter(address minter) public onlyOwner {
        require(!minters[minter], "AdvancedERC20: already a minter");
        minters[minter] = true;
        emit MinterAdded(minter);
    }
    
    function removeMinter(address minter) public onlyOwner {
        require(minters[minter], "AdvancedERC20: not a minter");
        minters[minter] = false;
        emit MinterRemoved(minter);
    }
    
    // Blacklist management
    function blacklist(address account) public onlyOwner {
        require(!blacklisted[account], "AdvancedERC20: already blacklisted");
        blacklisted[account] = true;
        emit Blacklisted(account);
    }
    
    function unblacklist(address account) public onlyOwner {
        require(blacklisted[account], "AdvancedERC20: not blacklisted");
        blacklisted[account] = false;
        emit Unblacklisted(account);
    }
    
    // Batch blacklist operations
    function batchBlacklist(address[] calldata accounts) external onlyOwner {
        for (uint256 i = 0; i < accounts.length; i++) {
            if (!blacklisted[accounts[i]]) {
                blacklisted[accounts[i]] = true;
                emit Blacklisted(accounts[i]);
            }
        }
    }
    
    function batchUnblacklist(address[] calldata accounts) external onlyOwner {
        for (uint256 i = 0; i < accounts.length; i++) {
            if (blacklisted[accounts[i]]) {
                blacklisted[accounts[i]] = false;
                emit Unblacklisted(accounts[i]);
            }
        }
    }
    
    // Batch mint to multiple addresses
    function batchMint(address[] calldata recipients, uint256[] calldata amounts) external onlyMinter {
        require(recipients.length == amounts.length, "AdvancedERC20: arrays length mismatch");
        
        uint256 totalAmount = 0;
        for (uint256 i = 0; i < amounts.length; i++) {
            totalAmount += amounts[i];
        }
        
        require(mintedSupply + totalAmount <= MAX_SUPPLY, "AdvancedERC20: exceeds max supply");
        
        for (uint256 i = 0; i < recipients.length; i++) {
            require(!blacklisted[recipients[i]], "AdvancedERC20: recipient is blacklisted");
            super.mint(recipients[i], amounts[i]);
        }
        
        mintedSupply += totalAmount;
    }
    
    // Emergency withdrawal function
    function emergencyWithdraw() external onlyOwner {
        payable(owner).transfer(address(this).balance);
    }
    
    // Get comprehensive token statistics
    function getTokenStats() external view returns (
        uint256 _totalSupply,
        uint256 _mintedSupply,
        uint256 _remainingSupply,
        uint256 _holderCount,
        bool _paused
    ) {
        return (
            totalSupply,
            mintedSupply,
            MAX_SUPPLY - mintedSupply,
            0, // Would need to implement holder tracking
            paused
        );
    }
    
    // Airdrop function for promotional distributions
    function airdrop(address[] calldata recipients, uint256 amount) external onlyOwner {
        require(recipients.length > 0, "AdvancedERC20: no recipients");
        
        uint256 totalAmount = recipients.length * amount;
        require(mintedSupply + totalAmount <= MAX_SUPPLY, "AdvancedERC20: exceeds max supply");
        
        for (uint256 i = 0; i < recipients.length; i++) {
            require(!blacklisted[recipients[i]], "AdvancedERC20: recipient is blacklisted");
            super.mint(recipients[i], amount);
        }
        
        mintedSupply += totalAmount;
    }
    
    // Vesting function for team/investor tokens
    struct VestingSchedule {
        uint256 totalAmount;
        uint256 releasedAmount;
        uint256 startTime;
        uint256 duration;
        bool revocable;
        bool revoked;
    }
    
    mapping(address => VestingSchedule) public vestingSchedules;
    
    event VestingScheduleCreated(address indexed beneficiary, uint256 amount, uint256 duration);
    event VestingScheduleRevoked(address indexed beneficiary);
    event TokensVested(address indexed beneficiary, uint256 amount);
    
    function createVestingSchedule(
        address beneficiary,
        uint256 amount,
        uint256 duration,
        bool revocable
    ) external onlyOwner notBlacklisted(beneficiary) {
        require(vestingSchedules[beneficiary].totalAmount == 0, "AdvancedERC20: vesting schedule already exists");
        require(amount > 0, "AdvancedERC20: amount must be > 0");
        require(duration > 0, "AdvancedERC20: duration must be > 0");
        
        vestingSchedules[beneficiary] = VestingSchedule({
            totalAmount: amount,
            releasedAmount: 0,
            startTime: block.timestamp,
            duration: duration,
            revocable: revocable,
            revoked: false
        });
        
        // Mint tokens to this contract for vesting
        mint(address(this), amount);
        
        emit VestingScheduleCreated(beneficiary, amount, duration);
    }
    
    function releaseVestedTokens(address beneficiary) external {
        VestingSchedule storage schedule = vestingSchedules[beneficiary];
        require(schedule.totalAmount > 0, "AdvancedERC20: no vesting schedule");
        require(!schedule.revoked, "AdvancedERC20: vesting schedule revoked");
        
        uint256 vestedAmount = calculateVestedAmount(beneficiary);
        uint256 releasableAmount = vestedAmount - schedule.releasedAmount;
        
        require(releasableAmount > 0, "AdvancedERC20: no tokens to release");
        
        schedule.releasedAmount += releasableAmount;
        _transfer(address(this), beneficiary, releasableAmount);
        
        emit TokensVested(beneficiary, releasableAmount);
    }
    
    function calculateVestedAmount(address beneficiary) public view returns (uint256) {
        VestingSchedule storage schedule = vestingSchedules[beneficiary];
        if (schedule.totalAmount == 0 || schedule.revoked) {
            return 0;
        }
        
        if (block.timestamp >= schedule.startTime + schedule.duration) {
            return schedule.totalAmount;
        }
        
        uint256 elapsed = block.timestamp - schedule.startTime;
        return (schedule.totalAmount * elapsed) / schedule.duration;
    }
    
    function revokeVestingSchedule(address beneficiary) external onlyOwner {
        VestingSchedule storage schedule = vestingSchedules[beneficiary];
        require(schedule.totalAmount > 0, "AdvancedERC20: no vesting schedule");
        require(schedule.revocable, "AdvancedERC20: vesting schedule not revocable");
        require(!schedule.revoked, "AdvancedERC20: vesting schedule already revoked");
        
        uint256 vestedAmount = calculateVestedAmount(beneficiary);
        uint256 releasableAmount = vestedAmount - schedule.releasedAmount;
        
        if (releasableAmount > 0) {
            schedule.releasedAmount += releasableAmount;
            _transfer(address(this), beneficiary, releasableAmount);
            emit TokensVested(beneficiary, releasableAmount);
        }
        
        schedule.revoked = true;
        
        // Return unvested tokens to owner
        uint256 unvestedAmount = schedule.totalAmount - schedule.releasedAmount;
        if (unvestedAmount > 0) {
            _transfer(address(this), owner, unvestedAmount);
        }
        
        emit VestingScheduleRevoked(beneficiary);
    }
}