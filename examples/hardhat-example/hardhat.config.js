require("@nomiclabs/hardhat-waffle");
require("@nomiclabs/hardhat-ethers");

module.exports = {
  solidity: {
    version: "0.8.4",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200
      }
    }
  },
  networks: {
    stellaris: {
      url: "http://localhost:3006",
      chainId: 1337,
      accounts: [
        // Add your private keys here
        // Example: "0x1234567890123456789012345678901234567890123456789012345678901234"
      ],
      gas: 2000000,
      gasPrice: 1000000000
    }
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts"
  }
};