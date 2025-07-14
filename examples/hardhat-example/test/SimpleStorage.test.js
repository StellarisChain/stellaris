const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SimpleStorage on Stellaris", function () {
  let simpleStorage;
  let owner;
  
  beforeEach(async function () {
    [owner] = await ethers.getSigners();
    
    const SimpleStorage = await ethers.getContractFactory("SimpleStorage");
    simpleStorage = await SimpleStorage.deploy();
    await simpleStorage.deployed();
  });
  
  it("Should set and get value", async function () {
    // Set value
    await simpleStorage.setValue(42);
    
    // Get value
    const value = await simpleStorage.getValue();
    expect(value).to.equal(42);
  });
  
  it("Should increment value", async function () {
    // Set initial value
    await simpleStorage.setValue(10);
    
    // Increment
    await simpleStorage.increment();
    
    // Check new value
    const value = await simpleStorage.getValue();
    expect(value).to.equal(11);
  });
  
  it("Should emit ValueChanged event", async function () {
    await expect(simpleStorage.setValue(100))
      .to.emit(simpleStorage, "ValueChanged")
      .withArgs(100);
  });
  
  it("Should handle multiple operations", async function () {
    // Set value
    await simpleStorage.setValue(5);
    expect(await simpleStorage.getValue()).to.equal(5);
    
    // Increment multiple times
    await simpleStorage.increment();
    await simpleStorage.increment();
    await simpleStorage.increment();
    
    // Check final value
    expect(await simpleStorage.getValue()).to.equal(8);
  });
});