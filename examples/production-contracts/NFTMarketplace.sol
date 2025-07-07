// SPDX-License-Identifier: MIT
pragma solidity ^0.8.4;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721Enumerable.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Counters.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";

/**
 * @title NFT Marketplace - Production-ready NFT marketplace with royalties and auctions
 * @dev Comprehensive marketplace supporting direct sales, auctions, and creator royalties
 */
contract NFTMarketplace is ERC721, ERC721Enumerable, ERC721URIStorage, Ownable, ReentrancyGuard {
    using Counters for Counters.Counter;
    using SafeMath for uint256;
    
    Counters.Counter private _tokenIdCounter;
    
    struct MarketItem {
        uint256 tokenId;
        address payable seller;
        address payable owner;
        address payable creator;
        uint256 price;
        bool sold;
        bool active;
        uint256 royaltyPercentage; // Basis points (100 = 1%)
    }
    
    struct Auction {
        uint256 tokenId;
        address payable seller;
        uint256 startingPrice;
        uint256 currentBid;
        address payable highestBidder;
        uint256 auctionEndTime;
        bool ended;
        bool exists;
    }
    
    struct Collection {
        string name;
        string description;
        address creator;
        uint256[] tokenIds;
        bool verified;
        uint256 floorPrice;
        uint256 totalVolume;
    }
    
    mapping(uint256 => MarketItem) public marketItems;
    mapping(uint256 => Auction) public auctions;
    mapping(uint256 => Collection) public collections;
    mapping(address => mapping(uint256 => uint256)) public pendingReturns; // bidder => auction => amount
    mapping(address => uint256[]) public userTokens;
    mapping(string => bool) public usedTokenURIs;
    
    uint256 public itemCount;
    uint256 public collectionCount;
    uint256 public marketplaceFeePercentage = 250; // 2.5%
    uint256 public constant MAX_ROYALTY_PERCENTAGE = 1000; // 10%
    uint256 public constant FEE_DENOMINATOR = 10000;
    
    event MarketItemCreated(
        uint256 indexed tokenId,
        address seller,
        address owner,
        address creator,
        uint256 price,
        uint256 royaltyPercentage
    );
    
    event MarketItemSold(
        uint256 indexed tokenId,
        address seller,
        address buyer,
        uint256 price
    );
    
    event AuctionCreated(
        uint256 indexed tokenId,
        address seller,
        uint256 startingPrice,
        uint256 duration
    );
    
    event AuctionBid(
        uint256 indexed tokenId,
        address bidder,
        uint256 amount
    );
    
    event AuctionEnded(
        uint256 indexed tokenId,
        address winner,
        uint256 winningBid
    );
    
    event CollectionCreated(
        uint256 indexed collectionId,
        string name,
        address creator
    );
    
    event RoyaltyPaid(
        uint256 indexed tokenId,
        address creator,
        uint256 amount
    );
    
    constructor() ERC721("Stellaris NFT Marketplace", "SNFT") {}
    
    /**
     * @dev Create a new NFT and list it on the marketplace
     */
    function createAndListNFT(
        string memory tokenURI,
        uint256 price,
        uint256 royaltyPercentage,
        uint256 collectionId
    ) external nonReentrant returns (uint256) {
        require(price > 0, "Price must be greater than zero");
        require(royaltyPercentage <= MAX_ROYALTY_PERCENTAGE, "Royalty too high");
        require(!usedTokenURIs[tokenURI], "Token URI already used");
        require(bytes(tokenURI).length > 0, "Token URI cannot be empty");
        
        uint256 newTokenId = _tokenIdCounter.current();
        _tokenIdCounter.increment();
        
        _safeMint(msg.sender, newTokenId);
        _setTokenURI(newTokenId, tokenURI);
        
        // Mark URI as used to prevent duplicates
        usedTokenURIs[tokenURI] = true;
        
        // Create market item
        marketItems[newTokenId] = MarketItem({
            tokenId: newTokenId,
            seller: payable(msg.sender),
            owner: payable(address(this)),
            creator: payable(msg.sender),
            price: price,
            sold: false,
            active: true,
            royaltyPercentage: royaltyPercentage
        });
        
        // Add to collection if specified
        if (collectionId < collectionCount) {
            collections[collectionId].tokenIds.push(newTokenId);
            
            // Update floor price
            if (collections[collectionId].floorPrice == 0 || price < collections[collectionId].floorPrice) {
                collections[collectionId].floorPrice = price;
            }
        }
        
        // Transfer NFT to marketplace for escrow
        _transfer(msg.sender, address(this), newTokenId);
        
        itemCount++;
        
        emit MarketItemCreated(
            newTokenId,
            msg.sender,
            address(this),
            msg.sender,
            price,
            royaltyPercentage
        );
        
        return newTokenId;
    }
    
    /**
     * @dev Buy an NFT from the marketplace
     */
    function buyNFT(uint256 tokenId) external payable nonReentrant {
        MarketItem storage item = marketItems[tokenId];
        require(item.active, "Item not active");
        require(!item.sold, "Item already sold");
        require(msg.value >= item.price, "Insufficient payment");
        require(msg.sender != item.seller, "Cannot buy your own item");
        
        // Calculate fees and royalties
        uint256 totalPrice = item.price;
        uint256 marketplaceFee = totalPrice.mul(marketplaceFeePercentage).div(FEE_DENOMINATOR);
        uint256 royaltyFee = totalPrice.mul(item.royaltyPercentage).div(FEE_DENOMINATOR);
        uint256 sellerAmount = totalPrice.sub(marketplaceFee).sub(royaltyFee);
        
        // Update item state
        item.sold = true;
        item.active = false;
        item.owner = payable(msg.sender);
        
        // Transfer NFT to buyer
        _transfer(address(this), msg.sender, tokenId);
        
        // Transfer payments
        item.seller.transfer(sellerAmount);
        
        // Pay royalty to creator (if different from seller)
        if (item.creator != item.seller && royaltyFee > 0) {
            item.creator.transfer(royaltyFee);
            emit RoyaltyPaid(tokenId, item.creator, royaltyFee);
        }
        
        // Marketplace fee stays in contract (can be withdrawn by owner)
        
        // Refund excess payment
        if (msg.value > totalPrice) {
            payable(msg.sender).transfer(msg.value.sub(totalPrice));
        }
        
        // Update user tokens
        userTokens[msg.sender].push(tokenId);
        
        emit MarketItemSold(tokenId, item.seller, msg.sender, totalPrice);
    }
    
    /**
     * @dev Create an auction for an NFT
     */
    function createAuction(
        uint256 tokenId,
        uint256 startingPrice,
        uint256 duration
    ) external nonReentrant {
        require(ownerOf(tokenId) == msg.sender, "Not token owner");
        require(startingPrice > 0, "Starting price must be greater than zero");
        require(duration >= 1 hours && duration <= 7 days, "Invalid duration");
        require(!auctions[tokenId].exists, "Auction already exists");
        
        // Transfer NFT to marketplace for escrow
        _transfer(msg.sender, address(this), tokenId);
        
        auctions[tokenId] = Auction({
            tokenId: tokenId,
            seller: payable(msg.sender),
            startingPrice: startingPrice,
            currentBid: 0,
            highestBidder: payable(address(0)),
            auctionEndTime: block.timestamp + duration,
            ended: false,
            exists: true
        });
        
        emit AuctionCreated(tokenId, msg.sender, startingPrice, duration);
    }
    
    /**
     * @dev Place a bid on an auction
     */
    function placeBid(uint256 tokenId) external payable nonReentrant {
        Auction storage auction = auctions[tokenId];
        require(auction.exists, "Auction does not exist");
        require(!auction.ended, "Auction has ended");
        require(block.timestamp < auction.auctionEndTime, "Auction time expired");
        require(msg.sender != auction.seller, "Cannot bid on your own auction");
        require(
            msg.value > auction.currentBid && msg.value >= auction.startingPrice,
            "Bid too low"
        );
        
        // Return previous bid to previous bidder
        if (auction.highestBidder != address(0)) {
            pendingReturns[auction.highestBidder][tokenId] += auction.currentBid;
        }
        
        auction.currentBid = msg.value;
        auction.highestBidder = payable(msg.sender);
        
        emit AuctionBid(tokenId, msg.sender, msg.value);
    }
    
    /**
     * @dev End an auction and transfer NFT to winner
     */
    function endAuction(uint256 tokenId) external nonReentrant {
        Auction storage auction = auctions[tokenId];
        require(auction.exists, "Auction does not exist");
        require(!auction.ended, "Auction already ended");
        require(
            block.timestamp >= auction.auctionEndTime || msg.sender == auction.seller,
            "Auction not yet ended"
        );
        
        auction.ended = true;
        
        if (auction.highestBidder != address(0)) {
            // Calculate fees and royalties
            MarketItem storage item = marketItems[tokenId];
            uint256 totalPrice = auction.currentBid;
            uint256 marketplaceFee = totalPrice.mul(marketplaceFeePercentage).div(FEE_DENOMINATOR);
            uint256 royaltyFee = totalPrice.mul(item.royaltyPercentage).div(FEE_DENOMINATOR);
            uint256 sellerAmount = totalPrice.sub(marketplaceFee).sub(royaltyFee);
            
            // Transfer NFT to winner
            _transfer(address(this), auction.highestBidder, tokenId);
            
            // Transfer payments
            auction.seller.transfer(sellerAmount);
            
            // Pay royalty to creator
            if (item.creator != auction.seller && royaltyFee > 0) {
                item.creator.transfer(royaltyFee);
                emit RoyaltyPaid(tokenId, item.creator, royaltyFee);
            }
            
            // Update user tokens
            userTokens[auction.highestBidder].push(tokenId);
            
            emit AuctionEnded(tokenId, auction.highestBidder, auction.currentBid);
        } else {
            // No bids, return NFT to seller
            _transfer(address(this), auction.seller, tokenId);
            emit AuctionEnded(tokenId, address(0), 0);
        }
    }
    
    /**
     * @dev Withdraw failed bid
     */
    function withdrawBid(uint256 tokenId) external nonReentrant {
        uint256 amount = pendingReturns[msg.sender][tokenId];
        require(amount > 0, "No pending returns");
        
        pendingReturns[msg.sender][tokenId] = 0;
        payable(msg.sender).transfer(amount);
    }
    
    /**
     * @dev Create a new collection
     */
    function createCollection(
        string memory name,
        string memory description
    ) external returns (uint256) {
        require(bytes(name).length > 0, "Name cannot be empty");
        
        uint256 collectionId = collectionCount++;
        
        collections[collectionId] = Collection({
            name: name,
            description: description,
            creator: msg.sender,
            tokenIds: new uint256[](0),
            verified: false,
            floorPrice: 0,
            totalVolume: 0
        });
        
        emit CollectionCreated(collectionId, name, msg.sender);
        return collectionId;
    }
    
    /**
     * @dev Verify a collection (owner only)
     */
    function verifyCollection(uint256 collectionId) external onlyOwner {
        require(collectionId < collectionCount, "Collection does not exist");
        collections[collectionId].verified = true;
    }
    
    /**
     * @dev Remove item from marketplace
     */
    function removeFromMarketplace(uint256 tokenId) external nonReentrant {
        MarketItem storage item = marketItems[tokenId];
        require(item.seller == msg.sender, "Not the seller");
        require(item.active && !item.sold, "Item not active");
        
        item.active = false;
        
        // Transfer NFT back to seller
        _transfer(address(this), msg.sender, tokenId);
    }
    
    /**
     * @dev Update marketplace fee (owner only)
     */
    function updateMarketplaceFee(uint256 newFeePercentage) external onlyOwner {
        require(newFeePercentage <= 1000, "Fee too high"); // Max 10%
        marketplaceFeePercentage = newFeePercentage;
    }
    
    /**
     * @dev Withdraw marketplace fees (owner only)
     */
    function withdrawFees() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "No fees to withdraw");
        payable(owner()).transfer(balance);
    }
    
    /**
     * @dev Get active market items
     */
    function getActiveMarketItems() external view returns (MarketItem[] memory) {
        uint256 activeItemCount = 0;
        
        // Count active items
        for (uint256 i = 0; i < itemCount; i++) {
            if (marketItems[i].active && !marketItems[i].sold) {
                activeItemCount++;
            }
        }
        
        // Create array of active items
        MarketItem[] memory items = new MarketItem[](activeItemCount);
        uint256 currentIndex = 0;
        
        for (uint256 i = 0; i < itemCount; i++) {
            if (marketItems[i].active && !marketItems[i].sold) {
                items[currentIndex] = marketItems[i];
                currentIndex++;
            }
        }
        
        return items;
    }
    
    /**
     * @dev Get user's NFTs
     */
    function getUserNFTs(address user) external view returns (uint256[] memory) {
        return userTokens[user];
    }
    
    /**
     * @dev Get collection tokens
     */
    function getCollectionTokens(uint256 collectionId) external view returns (uint256[] memory) {
        require(collectionId < collectionCount, "Collection does not exist");
        return collections[collectionId].tokenIds;
    }
    
    /**
     * @dev Get active auctions
     */
    function getActiveAuctions() external view returns (Auction[] memory) {
        uint256 activeAuctionCount = 0;
        
        // Count active auctions
        for (uint256 i = 0; i < itemCount; i++) {
            if (auctions[i].exists && !auctions[i].ended && block.timestamp < auctions[i].auctionEndTime) {
                activeAuctionCount++;
            }
        }
        
        // Create array of active auctions
        Auction[] memory activeAuctions = new Auction[](activeAuctionCount);
        uint256 currentIndex = 0;
        
        for (uint256 i = 0; i < itemCount; i++) {
            if (auctions[i].exists && !auctions[i].ended && block.timestamp < auctions[i].auctionEndTime) {
                activeAuctions[currentIndex] = auctions[i];
                currentIndex++;
            }
        }
        
        return activeAuctions;
    }
    
    /**
     * @dev Emergency function to recover stuck NFTs (owner only)
     */
    function emergencyRecoverNFT(uint256 tokenId, address to) external onlyOwner {
        require(ownerOf(tokenId) == address(this), "NFT not in marketplace");
        _transfer(address(this), to, tokenId);
    }
    
    // Required overrides
    function _beforeTokenTransfer(address from, address to, uint256 tokenId)
        internal
        override(ERC721, ERC721Enumerable)
    {
        super._beforeTokenTransfer(from, to, tokenId);
    }
    
    function _burn(uint256 tokenId) internal override(ERC721, ERC721URIStorage) {
        super._burn(tokenId);
    }
    
    function tokenURI(uint256 tokenId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (string memory)
    {
        return super.tokenURI(tokenId);
    }
    
    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721, ERC721Enumerable)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
}