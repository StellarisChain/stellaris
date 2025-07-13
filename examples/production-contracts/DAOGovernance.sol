// SPDX-License-Identifier: MIT
pragma solidity ^0.8.4;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";

/**
 * @title DAO Governance - Production-ready decentralized autonomous organization
 * @dev Comprehensive DAO with proposal creation, voting, execution, and treasury management
 */
contract DAOGovernance is Ownable, ReentrancyGuard {
    using SafeMath for uint256;
    
    struct Proposal {
        uint256 id;
        address proposer;
        string title;
        string description;
        address target;
        bytes callData;
        uint256 value;
        uint256 startTime;
        uint256 endTime;
        uint256 forVotes;
        uint256 againstVotes;
        uint256 abstainVotes;
        bool executed;
        bool cancelled;
        ProposalState state;
        mapping(address => Receipt) receipts;
    }
    
    struct Receipt {
        bool hasVoted;
        uint8 support; // 0 = against, 1 = for, 2 = abstain
        uint256 votes;
    }
    
    enum ProposalState {
        Pending,
        Active,
        Cancelled,
        Defeated,
        Succeeded,
        Queued,
        Expired,
        Executed
    }
    
    struct TreasuryAsset {
        address token;
        uint256 balance;
        bool isNative;
    }
    
    struct Member {
        address account;
        uint256 votingPower;
        uint256 delegatedPower;
        address delegateTo;
        uint256 joinTime;
        bool active;
    }
    
    // Core storage
    mapping(uint256 => Proposal) public proposals;
    mapping(address => Member) public members;
    mapping(address => address[]) public delegators; // delegate => list of delegators
    mapping(address => TreasuryAsset) public treasuryAssets;
    
    address[] public membersList;
    address[] public treasuryTokens;
    uint256 public proposalCount;
    
    // Governance parameters
    uint256 public votingDelay = 1 days; // Delay before voting starts
    uint256 public votingPeriod = 7 days; // How long voting lasts
    uint256 public proposalThreshold = 100000 * 10**18; // Min tokens to propose
    uint256 public quorumVotes = 400000 * 10**18; // Min votes for quorum
    uint256 public timelockDelay = 2 days; // Delay before execution
    
    // Timelock for executed proposals
    mapping(uint256 => uint256) public proposalEta;
    
    // Events
    event ProposalCreated(
        uint256 id,
        address proposer,
        address target,
        uint256 value,
        string title,
        string description,
        uint256 startTime,
        uint256 endTime
    );
    
    event VoteCast(
        address voter,
        uint256 proposalId,
        uint8 support,
        uint256 votes,
        string reason
    );
    
    event ProposalQueued(uint256 id, uint256 eta);
    event ProposalExecuted(uint256 id);
    event ProposalCancelled(uint256 id);
    
    event MemberAdded(address member, uint256 votingPower);
    event MemberRemoved(address member);
    event VotingPowerUpdated(address member, uint256 newPower);
    event DelegateChanged(address delegator, address fromDelegate, address toDelegate);
    
    event TreasuryDeposit(address token, uint256 amount);
    event TreasuryWithdraw(address token, uint256 amount, address recipient);
    
    modifier onlyMember() {
        require(members[msg.sender].active, "Not an active member");
        _;
    }
    
    modifier validProposal(uint256 proposalId) {
        require(proposalId < proposalCount, "Invalid proposal ID");
        _;
    }
    
    constructor() {
        // Add deployer as initial member
        _addMember(msg.sender, proposalThreshold);
    }
    
    /**
     * @dev Create a new proposal
     */
    function propose(
        address target,
        uint256 value,
        bytes memory callData,
        string memory title,
        string memory description
    ) external onlyMember returns (uint256) {
        require(
            getVotingPower(msg.sender) >= proposalThreshold,
            "Insufficient voting power to propose"
        );
        require(bytes(title).length > 0, "Title cannot be empty");
        require(target != address(0), "Invalid target address");
        
        uint256 proposalId = proposalCount++;
        uint256 startTime = block.timestamp + votingDelay;
        uint256 endTime = startTime + votingPeriod;
        
        Proposal storage proposal = proposals[proposalId];
        proposal.id = proposalId;
        proposal.proposer = msg.sender;
        proposal.title = title;
        proposal.description = description;
        proposal.target = target;
        proposal.callData = callData;
        proposal.value = value;
        proposal.startTime = startTime;
        proposal.endTime = endTime;
        proposal.state = ProposalState.Pending;
        
        emit ProposalCreated(
            proposalId,
            msg.sender,
            target,
            value,
            title,
            description,
            startTime,
            endTime
        );
        
        return proposalId;
    }
    
    /**
     * @dev Cast a vote on a proposal
     */
    function castVote(
        uint256 proposalId,
        uint8 support,
        string memory reason
    ) external validProposal(proposalId) onlyMember {
        Proposal storage proposal = proposals[proposalId];
        require(state(proposalId) == ProposalState.Active, "Voting not active");
        require(!proposal.receipts[msg.sender].hasVoted, "Already voted");
        require(support <= 2, "Invalid support value");
        
        uint256 votes = getVotingPower(msg.sender);
        require(votes > 0, "No voting power");
        
        proposal.receipts[msg.sender] = Receipt({
            hasVoted: true,
            support: support,
            votes: votes
        });
        
        if (support == 0) {
            proposal.againstVotes = proposal.againstVotes.add(votes);
        } else if (support == 1) {
            proposal.forVotes = proposal.forVotes.add(votes);
        } else {
            proposal.abstainVotes = proposal.abstainVotes.add(votes);
        }
        
        emit VoteCast(msg.sender, proposalId, support, votes, reason);
    }
    
    /**
     * @dev Queue a successful proposal for execution
     */
    function queue(uint256 proposalId) external validProposal(proposalId) {
        require(state(proposalId) == ProposalState.Succeeded, "Proposal not succeeded");
        
        uint256 eta = block.timestamp + timelockDelay;
        proposalEta[proposalId] = eta;
        proposals[proposalId].state = ProposalState.Queued;
        
        emit ProposalQueued(proposalId, eta);
    }
    
    /**
     * @dev Execute a queued proposal
     */
    function execute(uint256 proposalId) external validProposal(proposalId) nonReentrant {
        require(state(proposalId) == ProposalState.Queued, "Proposal not queued");
        require(block.timestamp >= proposalEta[proposalId], "Timelock not expired");
        require(block.timestamp <= proposalEta[proposalId] + 14 days, "Proposal expired");
        
        Proposal storage proposal = proposals[proposalId];
        proposal.executed = true;
        proposal.state = ProposalState.Executed;
        
        // Execute the proposal
        (bool success, ) = proposal.target.call{value: proposal.value}(proposal.callData);
        require(success, "Proposal execution failed");
        
        emit ProposalExecuted(proposalId);
    }
    
    /**
     * @dev Cancel a proposal (only proposer or owner)
     */
    function cancel(uint256 proposalId) external validProposal(proposalId) {
        Proposal storage proposal = proposals[proposalId];
        require(
            msg.sender == proposal.proposer || msg.sender == owner(),
            "Only proposer or owner can cancel"
        );
        require(
            state(proposalId) != ProposalState.Executed,
            "Cannot cancel executed proposal"
        );
        
        proposal.cancelled = true;
        proposal.state = ProposalState.Cancelled;
        
        emit ProposalCancelled(proposalId);
    }
    
    /**
     * @dev Add a new member to the DAO
     */
    function addMember(address account, uint256 votingPower) external onlyOwner {
        _addMember(account, votingPower);
    }
    
    /**
     * @dev Remove a member from the DAO
     */
    function removeMember(address account) external onlyOwner {
        require(members[account].active, "Member not active");
        
        members[account].active = false;
        members[account].votingPower = 0;
        
        // Remove from members list
        for (uint256 i = 0; i < membersList.length; i++) {
            if (membersList[i] == account) {
                membersList[i] = membersList[membersList.length - 1];
                membersList.pop();
                break;
            }
        }
        
        emit MemberRemoved(account);
    }
    
    /**
     * @dev Update member's voting power
     */
    function updateVotingPower(address account, uint256 newPower) external onlyOwner {
        require(members[account].active, "Member not active");
        
        members[account].votingPower = newPower;
        emit VotingPowerUpdated(account, newPower);
    }
    
    /**
     * @dev Delegate voting power to another member
     */
    function delegate(address delegatee) external onlyMember {
        require(members[delegatee].active, "Delegatee not active member");
        require(delegatee != msg.sender, "Cannot delegate to self");
        
        address oldDelegate = members[msg.sender].delegateTo;
        members[msg.sender].delegateTo = delegatee;
        
        // Update delegated power
        if (oldDelegate != address(0)) {
            members[oldDelegate].delegatedPower = members[oldDelegate].delegatedPower.sub(
                members[msg.sender].votingPower
            );
            _removeDelegator(oldDelegate, msg.sender);
        }
        
        members[delegatee].delegatedPower = members[delegatee].delegatedPower.add(
            members[msg.sender].votingPower
        );
        delegators[delegatee].push(msg.sender);
        
        emit DelegateChanged(msg.sender, oldDelegate, delegatee);
    }
    
    /**
     * @dev Deposit tokens to treasury
     */
    function depositToTreasury(address token, uint256 amount) external {
        if (token == address(0)) {
            // Native token deposit
            require(msg.value == amount, "Incorrect native token amount");
            treasuryAssets[token].balance = treasuryAssets[token].balance.add(amount);
            treasuryAssets[token].isNative = true;
        } else {
            // ERC20 token deposit
            IERC20(token).transferFrom(msg.sender, address(this), amount);
            treasuryAssets[token].balance = treasuryAssets[token].balance.add(amount);
            treasuryAssets[token].token = token;
        }
        
        // Add to treasury tokens list if new
        bool exists = false;
        for (uint256 i = 0; i < treasuryTokens.length; i++) {
            if (treasuryTokens[i] == token) {
                exists = true;
                break;
            }
        }
        if (!exists) {
            treasuryTokens.push(token);
        }
        
        emit TreasuryDeposit(token, amount);
    }
    
    /**
     * @dev Withdraw from treasury (only through governance)
     */
    function withdrawFromTreasury(
        address token,
        uint256 amount,
        address recipient
    ) external {
        require(msg.sender == address(this), "Only callable through governance");
        require(treasuryAssets[token].balance >= amount, "Insufficient treasury balance");
        require(recipient != address(0), "Invalid recipient");
        
        treasuryAssets[token].balance = treasuryAssets[token].balance.sub(amount);
        
        if (token == address(0)) {
            payable(recipient).transfer(amount);
        } else {
            IERC20(token).transfer(recipient, amount);
        }
        
        emit TreasuryWithdraw(token, amount, recipient);
    }
    
    /**
     * @dev Get proposal state
     */
    function state(uint256 proposalId) public view validProposal(proposalId) returns (ProposalState) {
        Proposal storage proposal = proposals[proposalId];
        
        if (proposal.cancelled) {
            return ProposalState.Cancelled;
        } else if (proposal.executed) {
            return ProposalState.Executed;
        } else if (block.timestamp < proposal.startTime) {
            return ProposalState.Pending;
        } else if (block.timestamp <= proposal.endTime) {
            return ProposalState.Active;
        } else if (proposal.forVotes <= proposal.againstVotes || proposal.forVotes < quorumVotes) {
            return ProposalState.Defeated;
        } else if (proposalEta[proposalId] == 0) {
            return ProposalState.Succeeded;
        } else if (block.timestamp >= proposalEta[proposalId] + 14 days) {
            return ProposalState.Expired;
        } else {
            return ProposalState.Queued;
        }
    }
    
    /**
     * @dev Get voting power including delegated power
     */
    function getVotingPower(address account) public view returns (uint256) {
        if (!members[account].active) return 0;
        return members[account].votingPower.add(members[account].delegatedPower);
    }
    
    /**
     * @dev Get proposal details
     */
    function getProposal(uint256 proposalId) external view validProposal(proposalId) returns (
        uint256 id,
        address proposer,
        string memory title,
        string memory description,
        address target,
        uint256 value,
        uint256 startTime,
        uint256 endTime,
        uint256 forVotes,
        uint256 againstVotes,
        uint256 abstainVotes,
        bool executed,
        bool cancelled,
        ProposalState currentState
    ) {
        Proposal storage proposal = proposals[proposalId];
        return (
            proposal.id,
            proposal.proposer,
            proposal.title,
            proposal.description,
            proposal.target,
            proposal.value,
            proposal.startTime,
            proposal.endTime,
            proposal.forVotes,
            proposal.againstVotes,
            proposal.abstainVotes,
            proposal.executed,
            proposal.cancelled,
            state(proposalId)
        );
    }
    
    /**
     * @dev Get member list
     */
    function getMembers() external view returns (address[] memory) {
        return membersList;
    }
    
    /**
     * @dev Get treasury assets
     */
    function getTreasuryAssets() external view returns (address[] memory, uint256[] memory) {
        uint256[] memory balances = new uint256[](treasuryTokens.length);
        for (uint256 i = 0; i < treasuryTokens.length; i++) {
            balances[i] = treasuryAssets[treasuryTokens[i]].balance;
        }
        return (treasuryTokens, balances);
    }
    
    /**
     * @dev Get active proposals
     */
    function getActiveProposals() external view returns (uint256[] memory) {
        uint256 activeCount = 0;
        
        // Count active proposals
        for (uint256 i = 0; i < proposalCount; i++) {
            if (state(i) == ProposalState.Active) {
                activeCount++;
            }
        }
        
        // Collect active proposal IDs
        uint256[] memory activeProposals = new uint256[](activeCount);
        uint256 index = 0;
        
        for (uint256 i = 0; i < proposalCount; i++) {
            if (state(i) == ProposalState.Active) {
                activeProposals[index] = i;
                index++;
            }
        }
        
        return activeProposals;
    }
    
    /**
     * @dev Update governance parameters (only through governance)
     */
    function updateGovernanceParams(
        uint256 newVotingDelay,
        uint256 newVotingPeriod,
        uint256 newProposalThreshold,
        uint256 newQuorumVotes,
        uint256 newTimelockDelay
    ) external {
        require(msg.sender == address(this), "Only callable through governance");
        require(newVotingDelay <= 7 days, "Voting delay too long");
        require(newVotingPeriod >= 1 days && newVotingPeriod <= 30 days, "Invalid voting period");
        require(newTimelockDelay >= 1 days && newTimelockDelay <= 30 days, "Invalid timelock delay");
        
        votingDelay = newVotingDelay;
        votingPeriod = newVotingPeriod;
        proposalThreshold = newProposalThreshold;
        quorumVotes = newQuorumVotes;
        timelockDelay = newTimelockDelay;
    }
    
    // Internal functions
    function _addMember(address account, uint256 votingPower) internal {
        require(account != address(0), "Invalid account");
        require(!members[account].active, "Member already exists");
        
        members[account] = Member({
            account: account,
            votingPower: votingPower,
            delegatedPower: 0,
            delegateTo: address(0),
            joinTime: block.timestamp,
            active: true
        });
        
        membersList.push(account);
        emit MemberAdded(account, votingPower);
    }
    
    function _removeDelegator(address delegate, address delegator) internal {
        address[] storage dels = delegators[delegate];
        for (uint256 i = 0; i < dels.length; i++) {
            if (dels[i] == delegator) {
                dels[i] = dels[dels.length - 1];
                dels.pop();
                break;
            }
        }
    }
    
    // Fallback to receive native tokens
    receive() external payable {
        treasuryAssets[address(0)].balance = treasuryAssets[address(0)].balance.add(msg.value);
        treasuryAssets[address(0)].isNative = true;
        emit TreasuryDeposit(address(0), msg.value);
    }
}