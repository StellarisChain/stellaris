const { ethers } = require("hardhat");

async function main() {
  console.log("🚀 Deploying SimpleStorage contract to Stellaris...");
  
  // Get the contract factory
  const SimpleStorage = await ethers.getContractFactory("SimpleStorage");
  
  // Deploy the contract
  console.log("📄 Deploying contract...");
  const simpleStorage = await SimpleStorage.deploy();
  
  // Wait for deployment
  await simpleStorage.deployed();
  
  console.log("✅ SimpleStorage deployed to:", simpleStorage.address);
  console.log("🔗 Transaction hash:", simpleStorage.deployTransaction.hash);
  
  // Test the contract
  console.log("\n🧪 Testing contract...");
  
  // Set a value
  console.log("📝 Setting value to 42...");
  const setTx = await simpleStorage.setValue(42);
  await setTx.wait();
  console.log("✅ Value set successfully");
  
  // Get the value
  console.log("📖 Getting value...");
  const value = await simpleStorage.getValue();
  console.log("📊 Current value:", value.toString());
  
  // Increment the value
  console.log("➕ Incrementing value...");
  const incTx = await simpleStorage.increment();
  await incTx.wait();
  console.log("✅ Value incremented successfully");
  
  // Get the new value
  const newValue = await simpleStorage.getValue();
  console.log("📊 New value:", newValue.toString());
  
  console.log("\n🎉 Deployment and testing complete!");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("❌ Error:", error);
    process.exit(1);
  });