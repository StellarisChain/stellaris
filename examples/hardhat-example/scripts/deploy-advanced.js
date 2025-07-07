/**
 * Comprehensive ERC-20 Token Deployment Script for Stellaris
 * 
 * This script demonstrates deploying multiple token contracts
 * and setting up advanced features like vesting and minting.
 */

const { ethers } = require("hardhat");

async function main() {
  console.log("🚀 Comprehensive ERC-20 Token Deployment to Stellaris");
  console.log("=" * 60);
  
  // Get the deployer account
  const [deployer, user1, user2, user3] = await ethers.getSigners();
  
  console.log("📋 Deployment Details:");
  console.log("  Deployer address:", deployer.address);
  console.log("  Network:", network.name);
  console.log("  Chain ID:", network.config.chainId);
  
  // Check deployer balance
  const balance = await deployer.getBalance();
  console.log("  Deployer balance:", ethers.utils.formatEther(balance), "STL");
  
  if (balance.lt(ethers.utils.parseEther("1"))) {
    console.log("⚠️  Warning: Low balance, deployment may fail");
  }
  
  console.log("\n📄 STEP 1: Deploying Simple Storage Contract");
  console.log("-" * 40);
  
  // Deploy SimpleStorage contract
  const SimpleStorage = await ethers.getContractFactory("SimpleStorage");
  const simpleStorage = await SimpleStorage.deploy();
  await simpleStorage.deployed();
  
  console.log("✅ SimpleStorage deployed to:", simpleStorage.address);
  console.log("🔗 Transaction hash:", simpleStorage.deployTransaction.hash);
  
  // Test SimpleStorage
  console.log("\n🧪 Testing SimpleStorage...");
  await simpleStorage.setValue(42);
  const value = await simpleStorage.getValue();
  console.log("  Set value to 42, got:", value.toString());
  
  console.log("\n📄 STEP 2: Deploying Basic ERC-20 Token");
  console.log("-" * 40);
  
  // Deploy StellarisToken
  const StellarisToken = await ethers.getContractFactory("StellarisToken");
  const stellarisToken = await StellarisToken.deploy(
    "Stellaris Token",
    "STK",
    18,
    1000000 // 1 million tokens
  );
  await stellarisToken.deployed();
  
  console.log("✅ StellarisToken deployed to:", stellarisToken.address);
  console.log("🔗 Transaction hash:", stellarisToken.deployTransaction.hash);
  
  // Get token info
  const tokenInfo = await stellarisToken.getTokenInfo();
  console.log("📊 Token Info:");
  console.log("  Name:", tokenInfo._name);
  console.log("  Symbol:", tokenInfo._symbol);
  console.log("  Decimals:", tokenInfo._decimals);
  console.log("  Total Supply:", ethers.utils.formatEther(tokenInfo._totalSupply));
  console.log("  Owner:", tokenInfo._owner);
  
  console.log("\n📄 STEP 3: Deploying Advanced ERC-20 Token");
  console.log("-" * 40);
  
  // Deploy AdvancedERC20
  const AdvancedERC20 = await ethers.getContractFactory("AdvancedERC20");
  const advancedToken = await AdvancedERC20.deploy(
    "Advanced Stellaris Token",
    "ASTK",
    500000 // 500K initial supply
  );
  await advancedToken.deployed();
  
  console.log("✅ AdvancedERC20 deployed to:", advancedToken.address);
  console.log("🔗 Transaction hash:", advancedToken.deployTransaction.hash);
  
  // Get advanced token stats
  const tokenStats = await advancedToken.getTokenStats();
  console.log("📊 Advanced Token Stats:");
  console.log("  Total Supply:", ethers.utils.formatEther(tokenStats._totalSupply));
  console.log("  Minted Supply:", ethers.utils.formatEther(tokenStats._mintedSupply));
  console.log("  Remaining Supply:", ethers.utils.formatEther(tokenStats._remainingSupply));
  console.log("  Paused:", tokenStats._paused);
  
  console.log("\n🎯 STEP 4: Demonstrating Token Operations");
  console.log("-" * 40);
  
  // Transfer tokens
  console.log("📤 Transferring tokens...");
  await stellarisToken.transfer(user1.address, ethers.utils.parseEther("1000"));
  await stellarisToken.transfer(user2.address, ethers.utils.parseEther("2000"));
  
  // Check balances
  const balance1 = await stellarisToken.balanceOf(user1.address);
  const balance2 = await stellarisToken.balanceOf(user2.address);
  console.log("  User1 balance:", ethers.utils.formatEther(balance1));
  console.log("  User2 balance:", ethers.utils.formatEther(balance2));
  
  // Approve and transferFrom
  console.log("\n✅ Testing approvals...");
  await stellarisToken.connect(user1).approve(user2.address, ethers.utils.parseEther("500"));
  const allowance = await stellarisToken.allowance(user1.address, user2.address);
  console.log("  Allowance set:", ethers.utils.formatEther(allowance));
  
  await stellarisToken.connect(user2).transferFrom(
    user1.address,
    user3.address,
    ethers.utils.parseEther("100")
  );
  
  const balance3 = await stellarisToken.balanceOf(user3.address);
  console.log("  User3 balance after transferFrom:", ethers.utils.formatEther(balance3));
  
  console.log("\n🎯 STEP 5: Advanced Token Features");
  console.log("-" * 40);
  
  // Add minter
  console.log("👥 Adding minter...");
  await advancedToken.addMinter(user1.address);
  
  // Mint tokens
  console.log("🎯 Minting tokens...");
  await advancedToken.connect(user1).mint(user2.address, ethers.utils.parseEther("10000"));
  
  const advancedBalance = await advancedToken.balanceOf(user2.address);
  console.log("  User2 advanced token balance:", ethers.utils.formatEther(advancedBalance));
  
  // Batch operations
  console.log("\n📦 Batch operations...");
  const recipients = [user1.address, user2.address, user3.address];
  const amounts = [
    ethers.utils.parseEther("100"),
    ethers.utils.parseEther("200"),
    ethers.utils.parseEther("300")
  ];
  
  await advancedToken.batchMint(recipients, amounts);
  console.log("  Batch mint completed for 3 recipients");
  
  // Multi-transfer
  await stellarisToken.multiTransfer(
    [user1.address, user2.address],
    [ethers.utils.parseEther("50"), ethers.utils.parseEther("75")]
  );
  console.log("  Multi-transfer completed");
  
  console.log("\n🔒 STEP 6: Security Features");
  console.log("-" * 40);
  
  // Blacklist demonstration
  console.log("⚫ Testing blacklist...");
  await advancedToken.blacklist(user3.address);
  console.log("  User3 blacklisted");
  
  try {
    await advancedToken.connect(user3).transfer(user1.address, ethers.utils.parseEther("1"));
    console.log("  ❌ Blacklist failed - transfer should have been blocked");
  } catch (error) {
    console.log("  ✅ Blacklist working - transfer blocked");
  }
  
  // Unblacklist
  await advancedToken.unblacklist(user3.address);
  console.log("  User3 unblacklisted");
  
  // Pause token
  console.log("\n⏸️  Testing pause functionality...");
  await advancedToken.pause();
  
  try {
    await advancedToken.connect(user1).transfer(user2.address, ethers.utils.parseEther("1"));
    console.log("  ❌ Pause failed - transfer should have been blocked");
  } catch (error) {
    console.log("  ✅ Pause working - transfer blocked");
  }
  
  // Unpause
  await advancedToken.unpause();
  console.log("  Token unpaused");
  
  console.log("\n⏰ STEP 7: Vesting Schedule");
  console.log("-" * 40);
  
  // Create vesting schedule
  const vestingAmount = ethers.utils.parseEther("1000");
  const vestingDuration = 86400; // 1 day for demo
  
  console.log("📅 Creating vesting schedule...");
  await advancedToken.createVestingSchedule(
    user2.address,
    vestingAmount,
    vestingDuration,
    true // revocable
  );
  
  console.log("  Vesting schedule created for User2");
  console.log("  Amount:", ethers.utils.formatEther(vestingAmount));
  console.log("  Duration:", vestingDuration, "seconds");
  
  // Check vested amount
  const vestedAmount = await advancedToken.calculateVestedAmount(user2.address);
  console.log("  Current vested amount:", ethers.utils.formatEther(vestedAmount));
  
  console.log("\n🎭 STEP 8: Event Monitoring");
  console.log("-" * 40);
  
  // Set up event listeners
  console.log("👂 Setting up event listeners...");
  
  let eventCount = 0;
  const maxEvents = 5;
  
  const transferFilter = stellarisToken.filters.Transfer();
  const approvalFilter = stellarisToken.filters.Approval();
  
  stellarisToken.on(transferFilter, (from, to, value, event) => {
    console.log(`🔄 Transfer: ${from} → ${to} (${ethers.utils.formatEther(value)} STK)`);
    eventCount++;
  });
  
  stellarisToken.on(approvalFilter, (owner, spender, value, event) => {
    console.log(`✅ Approval: ${owner} → ${spender} (${ethers.utils.formatEther(value)} STK)`);
    eventCount++;
  });
  
  // Generate some events
  console.log("📡 Generating events...");
  await stellarisToken.transfer(user1.address, ethers.utils.parseEther("10"));
  await stellarisToken.approve(user2.address, ethers.utils.parseEther("20"));
  await stellarisToken.transfer(user3.address, ethers.utils.parseEther("30"));
  
  // Wait for events
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  console.log("\n📊 STEP 9: Final Statistics");
  console.log("-" * 40);
  
  // Get final balances
  const finalBalances = await Promise.all([
    stellarisToken.balanceOf(deployer.address),
    stellarisToken.balanceOf(user1.address),
    stellarisToken.balanceOf(user2.address),
    stellarisToken.balanceOf(user3.address)
  ]);
  
  console.log("💰 Final Token Balances (STK):");
  console.log("  Deployer:", ethers.utils.formatEther(finalBalances[0]));
  console.log("  User1:", ethers.utils.formatEther(finalBalances[1]));
  console.log("  User2:", ethers.utils.formatEther(finalBalances[2]));
  console.log("  User3:", ethers.utils.formatEther(finalBalances[3]));
  
  // Get network stats
  const blockNumber = await ethers.provider.getBlockNumber();
  const gasPrice = await ethers.provider.getGasPrice();
  
  console.log("\n📊 Network Statistics:");
  console.log("  Current block:", blockNumber);
  console.log("  Gas price:", ethers.utils.formatUnits(gasPrice, "gwei"), "gwei");
  
  console.log("\n🎉 DEPLOYMENT COMPLETE!");
  console.log("=" * 60);
  console.log("📋 Contract Addresses:");
  console.log("  SimpleStorage:", simpleStorage.address);
  console.log("  StellarisToken:", stellarisToken.address);
  console.log("  AdvancedERC20:", advancedToken.address);
  
  console.log("\n🔧 Next Steps:");
  console.log("  1. Save the contract addresses above");
  console.log("  2. Use them in your frontend application");
  console.log("  3. Test with Web3.js examples");
  console.log("  4. Deploy to production");
  
  console.log("\n📚 Resources:");
  console.log("  • Web3.js examples: ../web3js-example/");
  console.log("  • Documentation: ../../docs/BPF_VM_GUIDE.md");
  console.log("  • Test suite: npm run test");
  
  // Clean up event listeners
  stellarisToken.removeAllListeners();
  
  return {
    simpleStorage: simpleStorage.address,
    stellarisToken: stellarisToken.address,
    advancedToken: advancedToken.address
  };
}

main()
  .then((addresses) => {
    console.log("\n✅ Deployment script completed successfully!");
    console.log("📄 Contract addresses:", addresses);
    process.exit(0);
  })
  .catch((error) => {
    console.error("❌ Deployment failed:", error);
    process.exit(1);
  });