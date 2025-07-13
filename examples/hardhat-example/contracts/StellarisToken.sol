// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title ERC20 Token Standard Implementation
 * @dev Implementation of the ERC20 interface with additional features
 */

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address recipient, uint256 amount) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
    
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
}

contract StellarisToken is IERC20 {
    string public name;
    string public symbol;
    uint8 public decimals;
    uint256 public override totalSupply;
    
    mapping(address => uint256) private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;
    
    address public owner;
    bool public paused = false;
    
    event Mint(address indexed to, uint256 amount);
    event Burn(address indexed from, uint256 amount);
    event Pause();
    event Unpause();
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    
    modifier onlyOwner() {
        require(msg.sender == owner, "StellarisToken: caller is not the owner");
        _;
    }
    
    modifier whenNotPaused() {
        require(!paused, "StellarisToken: token transfer while paused");
        _;
    }
    
    constructor(
        string memory _name,
        string memory _symbol,
        uint8 _decimals,
        uint256 _initialSupply
    ) {
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        totalSupply = _initialSupply * 10**_decimals;
        owner = msg.sender;
        
        _balances[msg.sender] = totalSupply;
        emit Transfer(address(0), msg.sender, totalSupply);
    }
    
    function balanceOf(address account) public view override returns (uint256) {
        return _balances[account];
    }
    
    function transfer(address recipient, uint256 amount) public override whenNotPaused returns (bool) {
        _transfer(msg.sender, recipient, amount);
        return true;
    }
    
    function allowance(address tokenOwner, address spender) public view override returns (uint256) {
        return _allowances[tokenOwner][spender];
    }
    
    function approve(address spender, uint256 amount) public override returns (bool) {
        _approve(msg.sender, spender, amount);
        return true;
    }
    
    function transferFrom(address sender, address recipient, uint256 amount) public override whenNotPaused returns (bool) {
        uint256 currentAllowance = _allowances[sender][msg.sender];
        require(currentAllowance >= amount, "StellarisToken: transfer amount exceeds allowance");
        
        _transfer(sender, recipient, amount);
        _approve(sender, msg.sender, currentAllowance - amount);
        
        return true;
    }
    
    function increaseAllowance(address spender, uint256 addedValue) public returns (bool) {
        _approve(msg.sender, spender, _allowances[msg.sender][spender] + addedValue);
        return true;
    }
    
    function decreaseAllowance(address spender, uint256 subtractedValue) public returns (bool) {
        uint256 currentAllowance = _allowances[msg.sender][spender];
        require(currentAllowance >= subtractedValue, "StellarisToken: decreased allowance below zero");
        
        _approve(msg.sender, spender, currentAllowance - subtractedValue);
        return true;
    }
    
    function mint(address to, uint256 amount) public onlyOwner {
        require(to != address(0), "StellarisToken: mint to the zero address");
        
        totalSupply += amount;
        _balances[to] += amount;
        
        emit Transfer(address(0), to, amount);
        emit Mint(to, amount);
    }
    
    function burn(uint256 amount) public {
        require(_balances[msg.sender] >= amount, "StellarisToken: burn amount exceeds balance");
        
        _balances[msg.sender] -= amount;
        totalSupply -= amount;
        
        emit Transfer(msg.sender, address(0), amount);
        emit Burn(msg.sender, amount);
    }
    
    function burnFrom(address account, uint256 amount) public {
        uint256 currentAllowance = _allowances[account][msg.sender];
        require(currentAllowance >= amount, "StellarisToken: burn amount exceeds allowance");
        require(_balances[account] >= amount, "StellarisToken: burn amount exceeds balance");
        
        _balances[account] -= amount;
        totalSupply -= amount;
        _approve(account, msg.sender, currentAllowance - amount);
        
        emit Transfer(account, address(0), amount);
        emit Burn(account, amount);
    }
    
    function pause() public onlyOwner {
        paused = true;
        emit Pause();
    }
    
    function unpause() public onlyOwner {
        paused = false;
        emit Unpause();
    }
    
    function transferOwnership(address newOwner) public onlyOwner {
        require(newOwner != address(0), "StellarisToken: new owner is the zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }
    
    function _transfer(address sender, address recipient, uint256 amount) internal {
        require(sender != address(0), "StellarisToken: transfer from the zero address");
        require(recipient != address(0), "StellarisToken: transfer to the zero address");
        require(_balances[sender] >= amount, "StellarisToken: transfer amount exceeds balance");
        
        _balances[sender] -= amount;
        _balances[recipient] += amount;
        
        emit Transfer(sender, recipient, amount);
    }
    
    function _approve(address tokenOwner, address spender, uint256 amount) internal {
        require(tokenOwner != address(0), "StellarisToken: approve from the zero address");
        require(spender != address(0), "StellarisToken: approve to the zero address");
        
        _allowances[tokenOwner][spender] = amount;
        emit Approval(tokenOwner, spender, amount);
    }
    
    // Additional utility functions
    function getTokenInfo() public view returns (
        string memory _name,
        string memory _symbol,
        uint8 _decimals,
        uint256 _totalSupply,
        address _owner,
        bool _paused
    ) {
        return (name, symbol, decimals, totalSupply, owner, paused);
    }
    
    function multiTransfer(address[] calldata recipients, uint256[] calldata amounts) public whenNotPaused returns (bool) {
        require(recipients.length == amounts.length, "StellarisToken: arrays length mismatch");
        
        for (uint256 i = 0; i < recipients.length; i++) {
            _transfer(msg.sender, recipients[i], amounts[i]);
        }
        
        return true;
    }
}