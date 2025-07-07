// SPDX-License-Identifier: MIT
pragma solidity ^0.8.4;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";

/**
 * @title DeFi Protocol - Production-ready decentralized exchange with liquidity pools
 * @dev Implements automated market maker (AMM) with yield farming capabilities
 */
contract DeFiProtocol is ReentrancyGuard, Ownable {
    using SafeMath for uint256;
    
    struct Pool {
        address tokenA;
        address tokenB;
        uint256 reserveA;
        uint256 reserveB;
        uint256 totalLiquidity;
        mapping(address => uint256) liquidityShares;
        uint256 feeRate; // Fee in basis points (100 = 1%)
        bool active;
    }
    
    struct StakingPool {
        address stakingToken;
        address rewardToken;
        uint256 totalStaked;
        uint256 rewardRate; // Rewards per block
        uint256 lastUpdateBlock;
        uint256 rewardPerTokenStored;
        mapping(address => uint256) userStaked;
        mapping(address => uint256) userRewardPerTokenPaid;
        mapping(address => uint256) rewards;
    }
    
    mapping(bytes32 => Pool) public pools;
    mapping(uint256 => StakingPool) public stakingPools;
    mapping(address => bool) public authorizedTokens;
    
    uint256 public poolCount;
    uint256 public stakingPoolCount;
    uint256 public constant MINIMUM_LIQUIDITY = 10**3;
    uint256 public constant FEE_DENOMINATOR = 10000;
    
    event PoolCreated(bytes32 indexed poolId, address tokenA, address tokenB);
    event LiquidityAdded(bytes32 indexed poolId, address provider, uint256 amountA, uint256 amountB, uint256 liquidity);
    event LiquidityRemoved(bytes32 indexed poolId, address provider, uint256 amountA, uint256 amountB, uint256 liquidity);
    event Swap(bytes32 indexed poolId, address user, address tokenIn, address tokenOut, uint256 amountIn, uint256 amountOut);
    event Staked(uint256 indexed poolId, address user, uint256 amount);
    event Withdrawn(uint256 indexed poolId, address user, uint256 amount);
    event RewardsClaimed(uint256 indexed poolId, address user, uint256 amount);
    
    constructor() {
        // Initialize with some common tokens
        authorizedTokens[address(0)] = true; // ETH
    }
    
    /**
     * @dev Create a new liquidity pool
     */
    function createPool(
        address tokenA,
        address tokenB,
        uint256 feeRate
    ) external onlyOwner returns (bytes32 poolId) {
        require(tokenA != tokenB, "Identical tokens");
        require(authorizedTokens[tokenA] && authorizedTokens[tokenB], "Unauthorized tokens");
        require(feeRate <= 1000, "Fee too high"); // Max 10%
        
        // Ensure consistent ordering
        if (tokenA > tokenB) {
            (tokenA, tokenB) = (tokenB, tokenA);
        }
        
        poolId = keccak256(abi.encodePacked(tokenA, tokenB));
        require(!pools[poolId].active, "Pool exists");
        
        Pool storage pool = pools[poolId];
        pool.tokenA = tokenA;
        pool.tokenB = tokenB;
        pool.feeRate = feeRate;
        pool.active = true;
        
        poolCount++;
        emit PoolCreated(poolId, tokenA, tokenB);
    }
    
    /**
     * @dev Add liquidity to a pool
     */
    function addLiquidity(
        bytes32 poolId,
        uint256 amountADesired,
        uint256 amountBDesired,
        uint256 amountAMin,
        uint256 amountBMin
    ) external nonReentrant returns (uint256 amountA, uint256 amountB, uint256 liquidity) {
        Pool storage pool = pools[poolId];
        require(pool.active, "Pool not active");
        
        (amountA, amountB) = _calculateLiquidityAmounts(
            pool,
            amountADesired,
            amountBDesired,
            amountAMin,
            amountBMin
        );
        
        // Transfer tokens
        IERC20(pool.tokenA).transferFrom(msg.sender, address(this), amountA);
        IERC20(pool.tokenB).transferFrom(msg.sender, address(this), amountB);
        
        // Calculate liquidity shares
        if (pool.totalLiquidity == 0) {
            liquidity = _sqrt(amountA.mul(amountB)).sub(MINIMUM_LIQUIDITY);
            pool.liquidityShares[address(0)] = MINIMUM_LIQUIDITY; // Lock minimum liquidity
        } else {
            liquidity = _min(
                amountA.mul(pool.totalLiquidity).div(pool.reserveA),
                amountB.mul(pool.totalLiquidity).div(pool.reserveB)
            );
        }
        
        require(liquidity > 0, "Insufficient liquidity minted");
        
        pool.liquidityShares[msg.sender] = pool.liquidityShares[msg.sender].add(liquidity);
        pool.totalLiquidity = pool.totalLiquidity.add(liquidity);
        pool.reserveA = pool.reserveA.add(amountA);
        pool.reserveB = pool.reserveB.add(amountB);
        
        emit LiquidityAdded(poolId, msg.sender, amountA, amountB, liquidity);
    }
    
    /**
     * @dev Remove liquidity from a pool
     */
    function removeLiquidity(
        bytes32 poolId,
        uint256 liquidity,
        uint256 amountAMin,
        uint256 amountBMin
    ) external nonReentrant returns (uint256 amountA, uint256 amountB) {
        Pool storage pool = pools[poolId];
        require(pool.active, "Pool not active");
        require(pool.liquidityShares[msg.sender] >= liquidity, "Insufficient liquidity");
        
        amountA = liquidity.mul(pool.reserveA).div(pool.totalLiquidity);
        amountB = liquidity.mul(pool.reserveB).div(pool.totalLiquidity);
        
        require(amountA >= amountAMin && amountB >= amountBMin, "Insufficient amounts");
        
        pool.liquidityShares[msg.sender] = pool.liquidityShares[msg.sender].sub(liquidity);
        pool.totalLiquidity = pool.totalLiquidity.sub(liquidity);
        pool.reserveA = pool.reserveA.sub(amountA);
        pool.reserveB = pool.reserveB.sub(amountB);
        
        IERC20(pool.tokenA).transfer(msg.sender, amountA);
        IERC20(pool.tokenB).transfer(msg.sender, amountB);
        
        emit LiquidityRemoved(poolId, msg.sender, amountA, amountB, liquidity);
    }
    
    /**
     * @dev Swap tokens in a pool
     */
    function swap(
        bytes32 poolId,
        address tokenIn,
        uint256 amountIn,
        uint256 amountOutMin
    ) external nonReentrant returns (uint256 amountOut) {
        Pool storage pool = pools[poolId];
        require(pool.active, "Pool not active");
        require(tokenIn == pool.tokenA || tokenIn == pool.tokenB, "Invalid token");
        
        bool isTokenA = tokenIn == pool.tokenA;
        address tokenOut = isTokenA ? pool.tokenB : pool.tokenA;
        uint256 reserveIn = isTokenA ? pool.reserveA : pool.reserveB;
        uint256 reserveOut = isTokenA ? pool.reserveB : pool.reserveA;
        
        // Calculate output amount with fee
        uint256 amountInWithFee = amountIn.mul(FEE_DENOMINATOR.sub(pool.feeRate));
        uint256 numerator = amountInWithFee.mul(reserveOut);
        uint256 denominator = reserveIn.mul(FEE_DENOMINATOR).add(amountInWithFee);
        amountOut = numerator.div(denominator);
        
        require(amountOut >= amountOutMin, "Insufficient output amount");
        require(amountOut < reserveOut, "Insufficient liquidity");
        
        // Update reserves
        if (isTokenA) {
            pool.reserveA = pool.reserveA.add(amountIn);
            pool.reserveB = pool.reserveB.sub(amountOut);
        } else {
            pool.reserveB = pool.reserveB.add(amountIn);
            pool.reserveA = pool.reserveA.sub(amountOut);
        }
        
        // Transfer tokens
        IERC20(tokenIn).transferFrom(msg.sender, address(this), amountIn);
        IERC20(tokenOut).transfer(msg.sender, amountOut);
        
        emit Swap(poolId, msg.sender, tokenIn, tokenOut, amountIn, amountOut);
    }
    
    /**
     * @dev Create a staking pool for yield farming
     */
    function createStakingPool(
        address stakingToken,
        address rewardToken,
        uint256 rewardRate
    ) external onlyOwner returns (uint256 poolId) {
        require(authorizedTokens[stakingToken], "Unauthorized staking token");
        require(authorizedTokens[rewardToken], "Unauthorized reward token");
        
        poolId = stakingPoolCount++;
        StakingPool storage stakingPool = stakingPools[poolId];
        stakingPool.stakingToken = stakingToken;
        stakingPool.rewardToken = rewardToken;
        stakingPool.rewardRate = rewardRate;
        stakingPool.lastUpdateBlock = block.number;
    }
    
    /**
     * @dev Stake tokens in a staking pool
     */
    function stake(uint256 poolId, uint256 amount) external nonReentrant {
        StakingPool storage stakingPool = stakingPools[poolId];
        require(stakingPool.stakingToken != address(0), "Invalid pool");
        
        _updateRewards(poolId, msg.sender);
        
        stakingPool.totalStaked = stakingPool.totalStaked.add(amount);
        stakingPool.userStaked[msg.sender] = stakingPool.userStaked[msg.sender].add(amount);
        
        IERC20(stakingPool.stakingToken).transferFrom(msg.sender, address(this), amount);
        
        emit Staked(poolId, msg.sender, amount);
    }
    
    /**
     * @dev Withdraw staked tokens
     */
    function withdraw(uint256 poolId, uint256 amount) external nonReentrant {
        StakingPool storage stakingPool = stakingPools[poolId];
        require(stakingPool.userStaked[msg.sender] >= amount, "Insufficient staked");
        
        _updateRewards(poolId, msg.sender);
        
        stakingPool.totalStaked = stakingPool.totalStaked.sub(amount);
        stakingPool.userStaked[msg.sender] = stakingPool.userStaked[msg.sender].sub(amount);
        
        IERC20(stakingPool.stakingToken).transfer(msg.sender, amount);
        
        emit Withdrawn(poolId, msg.sender, amount);
    }
    
    /**
     * @dev Claim staking rewards
     */
    function claimRewards(uint256 poolId) external nonReentrant {
        _updateRewards(poolId, msg.sender);
        
        StakingPool storage stakingPool = stakingPools[poolId];
        uint256 reward = stakingPool.rewards[msg.sender];
        
        if (reward > 0) {
            stakingPool.rewards[msg.sender] = 0;
            IERC20(stakingPool.rewardToken).transfer(msg.sender, reward);
            emit RewardsClaimed(poolId, msg.sender, reward);
        }
    }
    
    /**
     * @dev Add authorized token (owner only)
     */
    function addAuthorizedToken(address token) external onlyOwner {
        authorizedTokens[token] = true;
    }
    
    /**
     * @dev Get pool reserves
     */
    function getPoolReserves(bytes32 poolId) external view returns (uint256 reserveA, uint256 reserveB) {
        Pool storage pool = pools[poolId];
        return (pool.reserveA, pool.reserveB);
    }
    
    /**
     * @dev Get user liquidity
     */
    function getUserLiquidity(bytes32 poolId, address user) external view returns (uint256) {
        return pools[poolId].liquidityShares[user];
    }
    
    /**
     * @dev Get staking info
     */
    function getStakingInfo(uint256 poolId, address user) external view returns (
        uint256 staked,
        uint256 pendingRewards
    ) {
        StakingPool storage stakingPool = stakingPools[poolId];
        staked = stakingPool.userStaked[user];
        pendingRewards = _calculatePendingRewards(poolId, user);
    }
    
    // Internal functions
    function _calculateLiquidityAmounts(
        Pool storage pool,
        uint256 amountADesired,
        uint256 amountBDesired,
        uint256 amountAMin,
        uint256 amountBMin
    ) internal view returns (uint256 amountA, uint256 amountB) {
        if (pool.reserveA == 0 && pool.reserveB == 0) {
            (amountA, amountB) = (amountADesired, amountBDesired);
        } else {
            uint256 amountBOptimal = amountADesired.mul(pool.reserveB).div(pool.reserveA);
            if (amountBOptimal <= amountBDesired) {
                require(amountBOptimal >= amountBMin, "Insufficient B amount");
                (amountA, amountB) = (amountADesired, amountBOptimal);
            } else {
                uint256 amountAOptimal = amountBDesired.mul(pool.reserveA).div(pool.reserveB);
                assert(amountAOptimal <= amountADesired);
                require(amountAOptimal >= amountAMin, "Insufficient A amount");
                (amountA, amountB) = (amountAOptimal, amountBDesired);
            }
        }
    }
    
    function _updateRewards(uint256 poolId, address user) internal {
        StakingPool storage stakingPool = stakingPools[poolId];
        
        uint256 rewardPerToken = _calculateRewardPerToken(poolId);
        stakingPool.rewardPerTokenStored = rewardPerToken;
        stakingPool.lastUpdateBlock = block.number;
        
        if (user != address(0)) {
            stakingPool.rewards[user] = _calculatePendingRewards(poolId, user);
            stakingPool.userRewardPerTokenPaid[user] = rewardPerToken;
        }
    }
    
    function _calculateRewardPerToken(uint256 poolId) internal view returns (uint256) {
        StakingPool storage stakingPool = stakingPools[poolId];
        
        if (stakingPool.totalStaked == 0) {
            return stakingPool.rewardPerTokenStored;
        }
        
        uint256 blocksPassed = block.number.sub(stakingPool.lastUpdateBlock);
        uint256 rewardIncrement = blocksPassed.mul(stakingPool.rewardRate).mul(1e18).div(stakingPool.totalStaked);
        
        return stakingPool.rewardPerTokenStored.add(rewardIncrement);
    }
    
    function _calculatePendingRewards(uint256 poolId, address user) internal view returns (uint256) {
        StakingPool storage stakingPool = stakingPools[poolId];
        
        uint256 rewardPerToken = _calculateRewardPerToken(poolId);
        uint256 rewardPerTokenDiff = rewardPerToken.sub(stakingPool.userRewardPerTokenPaid[user]);
        uint256 newRewards = stakingPool.userStaked[user].mul(rewardPerTokenDiff).div(1e18);
        
        return stakingPool.rewards[user].add(newRewards);
    }
    
    function _sqrt(uint256 y) internal pure returns (uint256 z) {
        if (y > 3) {
            z = y;
            uint256 x = y / 2 + 1;
            while (x < z) {
                z = x;
                x = (y / x + x) / 2;
            }
        } else if (y != 0) {
            z = 1;
        }
    }
    
    function _min(uint256 a, uint256 b) internal pure returns (uint256) {
        return a < b ? a : b;
    }
}