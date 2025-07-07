/**
 * Comprehensive ERC-20 Token Test Suite
 * 
 * This test suite covers all aspects of the ERC-20 token contracts
 * including basic functionality, advanced features, and edge cases.
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("🪙 ERC-20 Token Test Suite", function() {
  let stellarisToken;
  let advancedToken;
  let owner;
  let user1;
  let user2;
  let user3;
  let minter;
  
  const INITIAL_SUPPLY = ethers.utils.parseEther("1000000");
  const TRANSFER_AMOUNT = ethers.utils.parseEther("1000");
  const APPROVE_AMOUNT = ethers.utils.parseEther("500");
  
  beforeEach(async function() {
    // Get signers
    [owner, user1, user2, user3, minter] = await ethers.getSigners();
    
    // Deploy StellarisToken
    const StellarisToken = await ethers.getContractFactory("StellarisToken");
    stellarisToken = await StellarisToken.deploy(
      "Test Stellaris Token",
      "TST",
      18,
      1000000 // 1 million tokens
    );
    await stellarisToken.deployed();
    
    // Deploy AdvancedERC20
    const AdvancedERC20 = await ethers.getContractFactory("AdvancedERC20");
    advancedToken = await AdvancedERC20.deploy(
      "Advanced Test Token",
      "ATT",
      500000 // 500K initial supply
    );
    await advancedToken.deployed();
  });
  
  describe("📋 Basic ERC-20 Functionality", function() {
    
    it("Should have correct initial values", async function() {
      const tokenInfo = await stellarisToken.getTokenInfo();
      
      expect(tokenInfo._name).to.equal("Test Stellaris Token");
      expect(tokenInfo._symbol).to.equal("TST");
      expect(tokenInfo._decimals).to.equal(18);
      expect(tokenInfo._totalSupply).to.equal(INITIAL_SUPPLY);
      expect(tokenInfo._owner).to.equal(owner.address);
      expect(tokenInfo._paused).to.be.false;
    });
    
    it("Should assign initial supply to owner", async function() {
      const ownerBalance = await stellarisToken.balanceOf(owner.address);
      expect(ownerBalance).to.equal(INITIAL_SUPPLY);
    });
    
    it("Should transfer tokens correctly", async function() {
      await stellarisToken.transfer(user1.address, TRANSFER_AMOUNT);
      
      const user1Balance = await stellarisToken.balanceOf(user1.address);
      const ownerBalance = await stellarisToken.balanceOf(owner.address);
      
      expect(user1Balance).to.equal(TRANSFER_AMOUNT);
      expect(ownerBalance).to.equal(INITIAL_SUPPLY.sub(TRANSFER_AMOUNT));
    });
    
    it("Should fail transfer with insufficient balance", async function() {
      await expect(
        stellarisToken.connect(user1).transfer(user2.address, TRANSFER_AMOUNT)
      ).to.be.revertedWith("StellarisToken: transfer amount exceeds balance");
    });
    
    it("Should approve and transferFrom correctly", async function() {
      // Transfer some tokens to user1 first
      await stellarisToken.transfer(user1.address, TRANSFER_AMOUNT);
      
      // Approve user2 to spend user1's tokens
      await stellarisToken.connect(user1).approve(user2.address, APPROVE_AMOUNT);
      
      // Check allowance
      const allowance = await stellarisToken.allowance(user1.address, user2.address);
      expect(allowance).to.equal(APPROVE_AMOUNT);
      
      // Transfer from user1 to user3 via user2
      await stellarisToken.connect(user2).transferFrom(
        user1.address,
        user3.address,
        APPROVE_AMOUNT
      );
      
      // Check balances
      const user1Balance = await stellarisToken.balanceOf(user1.address);
      const user3Balance = await stellarisToken.balanceOf(user3.address);
      const newAllowance = await stellarisToken.allowance(user1.address, user2.address);
      
      expect(user1Balance).to.equal(TRANSFER_AMOUNT.sub(APPROVE_AMOUNT));
      expect(user3Balance).to.equal(APPROVE_AMOUNT);
      expect(newAllowance).to.equal(0);
    });
    
    it("Should increase and decrease allowance", async function() {
      const initialAllowance = ethers.utils.parseEther("100");
      const increaseAmount = ethers.utils.parseEther("50");
      const decreaseAmount = ethers.utils.parseEther("25");
      
      // Initial approval
      await stellarisToken.approve(user1.address, initialAllowance);
      
      // Increase allowance
      await stellarisToken.increaseAllowance(user1.address, increaseAmount);
      let allowance = await stellarisToken.allowance(owner.address, user1.address);
      expect(allowance).to.equal(initialAllowance.add(increaseAmount));
      
      // Decrease allowance
      await stellarisToken.decreaseAllowance(user1.address, decreaseAmount);
      allowance = await stellarisToken.allowance(owner.address, user1.address);
      expect(allowance).to.equal(initialAllowance.add(increaseAmount).sub(decreaseAmount));
    });
    
  });
  
  describe("🎯 Minting and Burning", function() {
    
    it("Should mint tokens by owner", async function() {
      const mintAmount = ethers.utils.parseEther("1000");
      const initialSupply = await stellarisToken.totalSupply();
      
      await stellarisToken.mint(user1.address, mintAmount);
      
      const user1Balance = await stellarisToken.balanceOf(user1.address);
      const newSupply = await stellarisToken.totalSupply();
      
      expect(user1Balance).to.equal(mintAmount);
      expect(newSupply).to.equal(initialSupply.add(mintAmount));
    });
    
    it("Should fail minting by non-owner", async function() {
      await expect(
        stellarisToken.connect(user1).mint(user2.address, ethers.utils.parseEther("1000"))
      ).to.be.revertedWith("StellarisToken: caller is not the owner");
    });
    
    it("Should burn tokens", async function() {
      const burnAmount = ethers.utils.parseEther("1000");
      const initialBalance = await stellarisToken.balanceOf(owner.address);
      const initialSupply = await stellarisToken.totalSupply();
      
      await stellarisToken.burn(burnAmount);
      
      const newBalance = await stellarisToken.balanceOf(owner.address);
      const newSupply = await stellarisToken.totalSupply();
      
      expect(newBalance).to.equal(initialBalance.sub(burnAmount));
      expect(newSupply).to.equal(initialSupply.sub(burnAmount));
    });
    
    it("Should burn from approved account", async function() {
      const burnAmount = ethers.utils.parseEther("500");
      
      // Transfer tokens to user1
      await stellarisToken.transfer(user1.address, ethers.utils.parseEther("1000"));
      
      // Approve user2 to burn user1's tokens
      await stellarisToken.connect(user1).approve(user2.address, burnAmount);
      
      // Burn from user1 via user2
      await stellarisToken.connect(user2).burnFrom(user1.address, burnAmount);
      
      const user1Balance = await stellarisToken.balanceOf(user1.address);
      const allowance = await stellarisToken.allowance(user1.address, user2.address);
      
      expect(user1Balance).to.equal(ethers.utils.parseEther("500"));
      expect(allowance).to.equal(0);
    });
    
  });
  
  describe("⏸️ Pause Functionality", function() {
    
    it("Should pause and unpause by owner", async function() {
      // Pause
      await stellarisToken.pause();
      const tokenInfo = await stellarisToken.getTokenInfo();
      expect(tokenInfo._paused).to.be.true;
      
      // Unpause
      await stellarisToken.unpause();
      const tokenInfo2 = await stellarisToken.getTokenInfo();
      expect(tokenInfo2._paused).to.be.false;
    });
    
    it("Should block transfers when paused", async function() {
      await stellarisToken.pause();
      
      await expect(
        stellarisToken.transfer(user1.address, TRANSFER_AMOUNT)
      ).to.be.revertedWith("StellarisToken: token transfer while paused");
    });
    
    it("Should fail pause by non-owner", async function() {
      await expect(
        stellarisToken.connect(user1).pause()
      ).to.be.revertedWith("StellarisToken: caller is not the owner");
    });
    
  });
  
  describe("🔄 Multi-Transfer", function() {
    
    it("Should multi-transfer to multiple recipients", async function() {
      const recipients = [user1.address, user2.address, user3.address];
      const amounts = [
        ethers.utils.parseEther("100"),
        ethers.utils.parseEther("200"),
        ethers.utils.parseEther("300")
      ];
      
      await stellarisToken.multiTransfer(recipients, amounts);
      
      const balances = await Promise.all(
        recipients.map(addr => stellarisToken.balanceOf(addr))
      );
      
      expect(balances[0]).to.equal(amounts[0]);
      expect(balances[1]).to.equal(amounts[1]);
      expect(balances[2]).to.equal(amounts[2]);
    });
    
    it("Should fail multi-transfer with mismatched arrays", async function() {
      const recipients = [user1.address, user2.address];
      const amounts = [ethers.utils.parseEther("100")];
      
      await expect(
        stellarisToken.multiTransfer(recipients, amounts)
      ).to.be.revertedWith("StellarisToken: arrays length mismatch");
    });
    
  });
  
  describe("🔐 Advanced Token Features", function() {
    
    it("Should add and remove minters", async function() {
      // Add minter
      await advancedToken.addMinter(minter.address);
      expect(await advancedToken.minters(minter.address)).to.be.true;
      
      // Remove minter
      await advancedToken.removeMinter(minter.address);
      expect(await advancedToken.minters(minter.address)).to.be.false;
    });
    
    it("Should allow minters to mint", async function() {
      await advancedToken.addMinter(minter.address);
      
      const mintAmount = ethers.utils.parseEther("1000");
      await advancedToken.connect(minter).mint(user1.address, mintAmount);
      
      const balance = await advancedToken.balanceOf(user1.address);
      expect(balance).to.equal(mintAmount);
    });
    
    it("Should respect max supply limit", async function() {
      const maxSupply = ethers.utils.parseEther("10000000"); // 10 million
      const currentSupply = await advancedToken.totalSupply();
      const excessAmount = maxSupply.sub(currentSupply).add(1);
      
      await expect(
        advancedToken.mint(user1.address, excessAmount)
      ).to.be.revertedWith("AdvancedERC20: exceeds max supply");
    });
    
    it("Should blacklist and unblacklist addresses", async function() {
      // Blacklist user1
      await advancedToken.blacklist(user1.address);
      expect(await advancedToken.blacklisted(user1.address)).to.be.true;
      
      // Try to mint to blacklisted address (should fail)
      await expect(
        advancedToken.mint(user1.address, ethers.utils.parseEther("100"))
      ).to.be.revertedWith("AdvancedERC20: account is blacklisted");
      
      // Unblacklist
      await advancedToken.unblacklist(user1.address);
      expect(await advancedToken.blacklisted(user1.address)).to.be.false;
    });
    
    it("Should perform batch operations", async function() {
      const recipients = [user1.address, user2.address, user3.address];
      const amounts = [
        ethers.utils.parseEther("100"),
        ethers.utils.parseEther("200"),
        ethers.utils.parseEther("300")
      ];
      
      await advancedToken.batchMint(recipients, amounts);
      
      const balances = await Promise.all(
        recipients.map(addr => advancedToken.balanceOf(addr))
      );
      
      expect(balances[0]).to.equal(amounts[0]);
      expect(balances[1]).to.equal(amounts[1]);
      expect(balances[2]).to.equal(amounts[2]);
    });
    
    it("Should perform airdrop", async function() {
      const recipients = [user1.address, user2.address, user3.address];
      const airdropAmount = ethers.utils.parseEther("50");
      
      await advancedToken.airdrop(recipients, airdropAmount);
      
      const balances = await Promise.all(
        recipients.map(addr => advancedToken.balanceOf(addr))
      );
      
      balances.forEach(balance => {
        expect(balance).to.equal(airdropAmount);
      });
    });
    
  });
  
  describe("⏰ Vesting Functionality", function() {
    
    it("Should create vesting schedule", async function() {
      const vestingAmount = ethers.utils.parseEther("1000");
      const vestingDuration = 86400; // 1 day
      
      await advancedToken.createVestingSchedule(
        user1.address,
        vestingAmount,
        vestingDuration,
        true // revocable
      );
      
      const schedule = await advancedToken.vestingSchedules(user1.address);
      expect(schedule.totalAmount).to.equal(vestingAmount);
      expect(schedule.duration).to.equal(vestingDuration);
      expect(schedule.revocable).to.be.true;
    });
    
    it("Should calculate vested amount correctly", async function() {
      const vestingAmount = ethers.utils.parseEther("1000");
      const vestingDuration = 100; // 100 seconds for testing
      
      await advancedToken.createVestingSchedule(
        user1.address,
        vestingAmount,
        vestingDuration,
        true
      );
      
      // Initially, vested amount should be 0
      let vestedAmount = await advancedToken.calculateVestedAmount(user1.address);
      expect(vestedAmount).to.equal(0);
      
      // Advance time by 50 seconds (halfway through vesting)
      await ethers.provider.send("evm_increaseTime", [50]);
      await ethers.provider.send("evm_mine");
      
      vestedAmount = await advancedToken.calculateVestedAmount(user1.address);
      expect(vestedAmount).to.be.closeTo(vestingAmount.div(2), ethers.utils.parseEther("10"));
    });
    
    it("Should release vested tokens", async function() {
      const vestingAmount = ethers.utils.parseEther("1000");
      const vestingDuration = 100;
      
      await advancedToken.createVestingSchedule(
        user1.address,
        vestingAmount,
        vestingDuration,
        true
      );
      
      // Advance time to complete vesting
      await ethers.provider.send("evm_increaseTime", [vestingDuration]);
      await ethers.provider.send("evm_mine");
      
      // Release tokens
      await advancedToken.releaseVestedTokens(user1.address);
      
      const balance = await advancedToken.balanceOf(user1.address);
      expect(balance).to.equal(vestingAmount);
    });
    
    it("Should revoke vesting schedule", async function() {
      const vestingAmount = ethers.utils.parseEther("1000");
      const vestingDuration = 100;
      
      await advancedToken.createVestingSchedule(
        user1.address,
        vestingAmount,
        vestingDuration,
        true // revocable
      );
      
      // Advance time partially
      await ethers.provider.send("evm_increaseTime", [50]);
      await ethers.provider.send("evm_mine");
      
      const initialBalance = await advancedToken.balanceOf(user1.address);
      
      // Revoke vesting
      await advancedToken.revokeVestingSchedule(user1.address);
      
      const finalBalance = await advancedToken.balanceOf(user1.address);
      const schedule = await advancedToken.vestingSchedules(user1.address);
      
      expect(schedule.revoked).to.be.true;
      expect(finalBalance).to.be.gt(initialBalance); // Should receive some tokens
    });
    
  });
  
  describe("📡 Events", function() {
    
    it("Should emit Transfer event", async function() {
      await expect(stellarisToken.transfer(user1.address, TRANSFER_AMOUNT))
        .to.emit(stellarisToken, "Transfer")
        .withArgs(owner.address, user1.address, TRANSFER_AMOUNT);
    });
    
    it("Should emit Approval event", async function() {
      await expect(stellarisToken.approve(user1.address, APPROVE_AMOUNT))
        .to.emit(stellarisToken, "Approval")
        .withArgs(owner.address, user1.address, APPROVE_AMOUNT);
    });
    
    it("Should emit Mint event", async function() {
      const mintAmount = ethers.utils.parseEther("1000");
      await expect(stellarisToken.mint(user1.address, mintAmount))
        .to.emit(stellarisToken, "Mint")
        .withArgs(user1.address, mintAmount);
    });
    
    it("Should emit Burn event", async function() {
      const burnAmount = ethers.utils.parseEther("1000");
      await expect(stellarisToken.burn(burnAmount))
        .to.emit(stellarisToken, "Burn")
        .withArgs(owner.address, burnAmount);
    });
    
    it("Should emit Pause and Unpause events", async function() {
      await expect(stellarisToken.pause())
        .to.emit(stellarisToken, "Pause");
      
      await expect(stellarisToken.unpause())
        .to.emit(stellarisToken, "Unpause");
    });
    
  });
  
  describe("🔒 Security Tests", function() {
    
    it("Should prevent zero address transfers", async function() {
      await expect(
        stellarisToken.transfer(ethers.constants.AddressZero, TRANSFER_AMOUNT)
      ).to.be.revertedWith("StellarisToken: transfer to the zero address");
    });
    
    it("Should prevent zero address approvals", async function() {
      await expect(
        stellarisToken.approve(ethers.constants.AddressZero, APPROVE_AMOUNT)
      ).to.be.revertedWith("StellarisToken: approve to the zero address");
    });
    
    it("Should prevent zero address minting", async function() {
      await expect(
        stellarisToken.mint(ethers.constants.AddressZero, ethers.utils.parseEther("1000"))
      ).to.be.revertedWith("StellarisToken: mint to the zero address");
    });
    
    it("Should prevent overflow in allowance operations", async function() {
      const maxUint256 = ethers.constants.MaxUint256;
      
      // Approve maximum amount
      await stellarisToken.approve(user1.address, maxUint256);
      
      // Try to increase allowance (should not overflow)
      await expect(
        stellarisToken.increaseAllowance(user1.address, 1)
      ).to.not.be.reverted;
    });
    
  });
  
  describe("📊 Gas Optimization Tests", function() {
    
    it("Should be gas efficient for basic operations", async function() {
      const tx1 = await stellarisToken.transfer(user1.address, TRANSFER_AMOUNT);
      const receipt1 = await tx1.wait();
      
      const tx2 = await stellarisToken.approve(user1.address, APPROVE_AMOUNT);
      const receipt2 = await tx2.wait();
      
      console.log("    Gas used for transfer:", receipt1.gasUsed.toString());
      console.log("    Gas used for approval:", receipt2.gasUsed.toString());
      
      // Basic checks - adjust limits based on your requirements
      expect(receipt1.gasUsed).to.be.lt(100000);
      expect(receipt2.gasUsed).to.be.lt(100000);
    });
    
    it("Should be efficient for batch operations", async function() {
      const recipients = [user1.address, user2.address, user3.address];
      const amounts = [
        ethers.utils.parseEther("100"),
        ethers.utils.parseEther("200"),
        ethers.utils.parseEther("300")
      ];
      
      const tx = await stellarisToken.multiTransfer(recipients, amounts);
      const receipt = await tx.wait();
      
      console.log("    Gas used for multi-transfer:", receipt.gasUsed.toString());
      
      // Should be more efficient than individual transfers
      expect(receipt.gasUsed).to.be.lt(300000); // Adjust based on requirements
    });
    
  });
  
});