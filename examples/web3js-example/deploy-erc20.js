/**
 * ERC-20 Token Deployment Script for Stellaris
 * 
 * This script demonstrates how to deploy an ERC-20 token contract
 * to the Stellaris blockchain using Web3.js
 */

const Web3 = require('web3');
require('dotenv').config();

// ERC-20 Token Contract ABI
const TOKEN_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "_name", "type": "string"},
            {"internalType": "string", "name": "_symbol", "type": "string"},
            {"internalType": "uint8", "name": "_decimals", "type": "uint8"},
            {"internalType": "uint256", "name": "_initialSupply", "type": "uint256"}
        ],
        "stateMutability": "nonpayable",
        "type": "constructor"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "internalType": "address", "name": "owner", "type": "address"},
            {"indexed": true, "internalType": "address", "name": "spender", "type": "address"},
            {"indexed": false, "internalType": "uint256", "name": "value", "type": "uint256"}
        ],
        "name": "Approval",
        "type": "event"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "internalType": "address", "name": "from", "type": "address"},
            {"indexed": false, "internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "Burn",
        "type": "event"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": false, "internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "Mint",
        "type": "event"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "internalType": "address", "name": "previousOwner", "type": "address"},
            {"indexed": true, "internalType": "address", "name": "newOwner", "type": "address"}
        ],
        "name": "OwnershipTransferred",
        "type": "event"
    },
    {
        "anonymous": false,
        "inputs": [],
        "name": "Pause",
        "type": "event"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "internalType": "address", "name": "from", "type": "address"},
            {"indexed": true, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": false, "internalType": "uint256", "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    },
    {
        "anonymous": false,
        "inputs": [],
        "name": "Unpause",
        "type": "event"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "burn",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "burnFrom",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "subtractedValue", "type": "uint256"}
        ],
        "name": "decreaseAllowance",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getTokenInfo",
        "outputs": [
            {"internalType": "string", "name": "_name", "type": "string"},
            {"internalType": "string", "name": "_symbol", "type": "string"},
            {"internalType": "uint8", "name": "_decimals", "type": "uint8"},
            {"internalType": "uint256", "name": "_totalSupply", "type": "uint256"},
            {"internalType": "address", "name": "_owner", "type": "address"},
            {"internalType": "bool", "name": "_paused", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "addedValue", "type": "uint256"}
        ],
        "name": "increaseAllowance",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "mint",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address[]", "name": "recipients", "type": "address[]"},
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
        ],
        "name": "multiTransfer",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "name",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "owner",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "pause",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "paused",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "sender", "type": "address"},
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "transferFrom",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "newOwner", "type": "address"}],
        "name": "transferOwnership",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "unpause",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
];

// Compiled bytecode for the StellarisToken contract
const TOKEN_BYTECODE = "0x608060405234801561001057600080fd5b50604051611e2a380380611e2a83398101604081905261002f9161020a565b8351610042906000906020870190610117565b508251610056906001906020860190610117565b5060028054600160a01b600160a81b031916600160a01b60ff851602179055816100818260ff1661029a565b61008b91906102b9565b600381905533600081815260046020908152604080832085905551938452919290917fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef910160405180910390a35050505050610317565b82805461012390610307565b90600052602060002090601f016020900481019282610145576000855561018b565b82601f1061015e57805160ff191683800117855561018b565b8280016001018555821561018b579182015b8281111561018b578251825591602001919060010190610170565b5061019792915061019b565b5090565b5b80821115610197576000815560010161019c565b634e487b7160e01b600052604160045260246000fd5b600082601f8301126101d757600080fd5b81516001600160401b03808211156101f1576101f16101b0565b604051601f8301601f19908116603f01168101908282118183101715610219576102196101b0565b8160405283815260209250868385880101111561023557600080fd5b600091505b83821015610257578582018301518183018401529082019061023a565b83821115610268576000838583010152505b9695505050505050565b600060ff8216905092915050565b61028b81610272565b811461029657600080fd5b50565b600082198211156102b457634e487b7160e01b600052601160045260246000fd5b500190565b60008160001904831182151516156102e157634e487b7160e01b600052601160045260246000fd5b500290565b600181811c908216806102fa57607f821691505b6020821081141561030b57634e487b7160e01b600052602260045260246000fd5b50919050565b611b0480610326000396000f3fe608060405234801561001057600080fd5b50600436106101735760003560e01c8063715018a6116100de578063a457c2d711610097578063d505accf11610071578063d505accf1461034d578063dd62ed3e14610360578063f2fde38b14610373578063f46eccc41461038657600080fd5b8063a457c2d714610321578063a9059cbb14610334578063dd46706414610347578063dd62ed3e14610360578063f2fde38b14610373578063f46eccc41461038657600080fd5b8063715018a6146102d65780638456cb59146102de5780638da5cb5b146102e657806395d89b41146102f95780639dc29fac14610301578063a39744b71461031457600080fd5b8063395093511161013057806339509351146102615780633f4ba83a1461027457806342966c681461027c5780635c975abb1461028f57806370a08231146102a05780637065cb48146102c357600080fd5b806306fdde0314610178578063095ea7b3146101965780631249c58b146101b957806318160ddd146101c357806323b872dd146101d5578063313ce567146101e8575b600080fd5b610180610399565b60405161018d9190611850565b60405180910390f35b6101a96101a43660046118a6565b61042b565b604051901515815260200161018d565b6101c1610441565b005b6003545b60405190815260200161018d565b6101a96101e33660046118d0565b610482565b60025474010000000000000000000000000000000000000000900460ff1660405160ff909116815260200161018d565b6101a961021f3660046118a6565b610536565b6101c1610232366004611901565b610575565b6101a96102453660046118a6565b6105cc565b6101c161025836600461191b565b610605565b6101a961026f3660046118a6565b6106c7565b6101c1610703565b6101c161028a36600461191b565b610736565b60025474010000000000000000000000000000000000000000900460ff166101a9565b6101c76102ae366004611901565b6001600160a01b031660009081526004602052604090205490565b6101c16102d1366004611901565b610743565b6101c16107a5565b6101c16107db565b60025461010090046001600160a01b03166101f0565b610180610810565b6101c161030f3660046118a6565b61081f565b6101c1610322366004611940565b610849565b6101a961032f3660046118a6565b610874565b6101a96103423660046118a6565b610913565b6101c161035536600461191b565b610920565b6101c761036e3660046119c5565b610955565b6101c1610381366004611901565b610980565b6101a9610394366004611901565b6109e1565b6060600080546103a8906119f8565b80601f01602080910402602001604051908101604052809291908181526020018280546103d4906119f8565b80156104215780601f106103f657610100808354040283529160200191610421565b820191906000526020600020905b81548152906001019060200180831161040457829003601f168201915b5050505050905090565b6000610438338484610a16565b50600192915050565b600254600160a01b900460ff16156104745760405162461bcd60e51b815260040161046b90611a33565b60405180910390fd5b61047f336001610b3b565b50565b6000610497848484610b3b565b6001600160a01b03841660009081526005602090815260408083203384529091529020548281101561051c5760405162461bcd60e51b815260206004820152602860248201527f45524332303a207472616e7366657220616d6f756e74206578636565647320616044820152676c6c6f77616e636560c01b606482015260840161046b565b6105298533858403610a16565b60019150505b9392505050565b3360008181526005602090815260408083206001600160a01b038716845290915281205490916104389185906105709086906119f8565b610a16565b6002546001600160a01b036101009091041633146105a55760405162461bcd60e51b815260040161046b90611a6a565b6001600160a01b03166000908152600660205260409020805460ff19811660ff90911615179055565b60025460009074010000000000000000000000000000000000000000900460ff16156105fc5760405162461bcd60e51b815260040161046b90611a33565b6104388383610c7a565b6002546001600160a01b036101009091041633146106355760405162461bcd60e51b815260040161046b90611a6a565b6001600160a01b03811660009081526006602052604090205460ff161561066e5760405162461bcd60e51b815260040161046b90611a9f565b6106783382610d4e565b50565b6001600160a01b0383166000908152600660205260408120548390829060ff16156106b85760405162461bcd60e51b815260040161046b90611a33565b6106c28484610dd7565b61052f565b3360008181526005602090815260408083206001600160a01b038716845290915281205490916104389185906105709086906119f8565b60025474010000000000000000000000000000000000000000900460ff166107315760405162461bcd60e51b815260040161046b90611ad4565b610740336001610b3b565b50565b6002546001600160a01b036101009091041633146107735760405162461bcd60e51b815260040161046b90611a6a565b6001600160a01b03166000908152600660205260409020805460ff19811660ff90911615179055565b6002546001600160a01b036101009091041633146107d55760405162461bcd60e51b815260040161046b90611a6a565b6107dd610e46565b565b6002546001600160a01b0361010090910416331461080f5760405162461bcd60e51b815260040161046b90611a6a565b6107dd610e80565b6060600180546103a8906119f8565b60025474010000000000000000000000000000000000000000900460ff16156108455760405162461bcd60e51b815260040161046b90611a33565b6107408282610ec1565b6002546001600160a01b036101009091041633146108795760405162461bcd60e51b815260040161046b90611a6a565b61088c8260026001600160a01b0316610f6d565b60025461010090046001600160a01b031633146108bb5760405162461bcd60e51b815260040161046b90611a6a565b6108c6600083610d4e565b6002805460ff60a01b1916600160a01b179055565b3360008181526005602090815260408083206001600160a01b0387168452909152812054909161043891859061057090866119f8565b6001600160a01b0383166000908152600660205260408120548390829060ff161561095c5760405162461bcd60e51b815260040161046b90611a33565b6109c1338484610b3b565b6000610930338484610b3b565b600254600160a01b900460ff16156109545760405162461bcd60e51b815260040161046b90611a33565b6104388383610c7a565b6001600160a01b03918216600090815260056020908152604080832093909416825291909152205490565b6002546001600160a01b036101009091041633146109b05760405162461bcd60e51b815260040161046b90611a6a565b6109b9816110a4565b60025473ffffffffffffffffffffffffffffffffffffffff19166101006001600160a01b0392831681021790915590565b6001600160a01b03166000908152600660205260409020546001600160a01b0316915050565b6001600160a01b038316610a785760405162461bcd60e51b8152602060048201526024808201527f45524332303a20617070726f76652066726f6d20746865207a65726f206164646044820152637265737360e01b606482015260840161046b565b6001600160a01b038216610ad95760405162461bcd60e51b815260206004820152602260248201527f45524332303a20617070726f766520746f20746865207a65726f206164647265604482015261737360f01b606482015260840161046b565b6001600160a01b0383811660008181526005602090815260408083209487168084529482529182902085905590518481527f8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925910160405180910390a3505050565b6001600160a01b038316610b9f5760405162461bcd60e51b815260206004820152602560248201527f45524332303a207472616e736665722066726f6d20746865207a65726f206164604482015264647265737360d81b606482015260840161046b565b6001600160a01b038216610c015760405162461bcd60e51b815260206004820152602360248201527f45524332303a207472616e7366657220746f20746865207a65726f206164647260448201526265737360e81b606482015260840161046b565b6001600160a01b03831660009081526004602052604090205481811015610c795760405162461bcd60e51b815260206004820152602660248201527f45524332303a207472616e7366657220616d6f756e7420657863656564732062604482015265616c616e636560d01b606482015260840161046b565b6001600160a01b03808516600090815260046020526040808220858503905591851681529081208054849290610cb0908490611b0d565b92505081905550826001600160a01b0316846001600160a01b03167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef84604051610cfc91815260200190565b60405180910390a350505050565b6001600160a01b038216610d615760405162461bcd60e51b815260206004820152602160248201527f45524332303a206275726e2066726f6d20746865207a65726f206164647265736044820152607360f81b606482015260840161046b565b6001600160a01b03821660009081526004602052604090205481811015610dd15760405162461bcd60e51b815260206004820152602260248201527f45524332303a206275726e20616d6f756e7420657863656564732062616c616e604482015261636560f01b606482015260840161046b565b6001600160a01b0383166000908152600460205260408120838303905560038054849290610e00908490611b25565b90915550506040518281526000906001600160a01b038516907fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef9060200160405180910390a3505050565b600254600160a01b900460ff16610e6f5760405162461bcd60e51b815260040161046b90611b3c565b6002805460ff60a01b19169055565b600254600160a01b900460ff1615610eaa5760405162461bcd60e51b815260040161046b90611a33565b6002805460ff60a01b1916600160a01b179055565b6001600160a01b038216610f175760405162461bcd60e51b815260206004820152601f60248201527f45524332303a206d696e7420746f20746865207a65726f206164647265737300604482015260640161046b565b8060036000828254610f299190611b0d565b90915550506001600160a01b03821660009081526004602052604081208054839290610f56908490611b0d565b90915550506040518181526001600160a01b038316906000907fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef9060200160405180910390a35050565b6001600160a01b03841660009081526005602090815260408083203384529091529020548281101561100a5760405162461bcd60e51b815260206004820152602560248201527f45524332303a206275726e20616d6f756e74206578636565647320616c6c6f77604482015264616e636560d81b606482015260840161046b565b6001600160a01b0384166000908152600460205260409020548281101561103b5760405162461bcd60e51b815260040161046b90611b73565b6001600160a01b0385166000908152600460205260408120838303905560038054849290611069908490611b25565b90915550506001600160a01b03851660009081526005602090815260408083203384529091528120838303905560405182815285919060009060008051602061190f8339815191529060200160405180910390a350505050565b6001600160a01b03811661111a5760405162461bcd60e51b815260206004820152602660248201527f4f776e61626c653a206e6577206f776e657220697320746865207a65726f206160448201526564647265737360d01b606482015260840161046b565b6002546040516001600160a01b0380841692610100900416907f8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e090600090a3600280546001600160a01b0390921661010002610100600160a81b0319909216919091179055565b600060208083528351808285015260005b8181101561187d57858101830151858201604001528201611861565b8181111561188f576000604083870101525b50601f01601f1916929092016040019392505050565b80356001600160a01b03811681146118bd57600080fd5b919050565b6000602082840312156118d457600080fd5b6118dd826118a6565b9392505050565b600080604083850312156118f757600080fd5b61190083611191565b9150611909602084016118a6565b90509250929050565b6000806040838503121561192557600080fd5b61192e836118a6565b946020939093013593505050565b60006020828403121561194e57600080fd5b81356118dd816119b1565b60006020828403121561196b57600080fd5b5035919050565b60006020828403121561198457600080fd5b81356118dd816119b1565b6000602082840312156119a157600080fd5b6118dd826118a6565b6001600160a01b038116811461047f57600080fd5b600080604083850312156119d857600080fd5b6119e1836118a6565b9150602083013580151581146119f657600080fd5b809150509250929050565b600181811c90821680611a1457607f821691505b60208210811415611a3557634e487b7160e01b600052602260045260246000fd5b50919050565b6020808252601f908201527f5468697320746f6b656e206973206e6f74207472616e7366657261626c6500604082015260600190565b60208082526018908201527f4f776e61626c653a2063616c6c6572206973206e6f74206f776e65720000604082015260600190565b60208082526017908201527f4163636f756e7420697320616c72656164792066726f7a656e000000000000604082015260600190565b60208082526014908201527f5061757361626c653a206e6f74207061757365640000000000000000000000604082015260600190565b634e487b7160e01b600052601160045260246000fd5b60008219821115611b2057611b20611af7565b500190565b600082821015611b3757611b37611af7565b500390565b60208082526010908201526f14185d5cd8589b194e881c185d5cd95960821b604082015260600190565b60208082526022908201527f45524332303a206275726e20616d6f756e7420657863656564732062616c616e604082015261636560f01b6060820152608001905056fea2646970667358221220ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef64736f6c634300080a0033";

class TokenDeployer {
    constructor() {
        this.web3 = new Web3(process.env.STELLARIS_RPC_URL || 'http://localhost:3006');
        this.account = null;
        
        if (process.env.PRIVATE_KEY) {
            this.account = this.web3.eth.accounts.privateKeyToAccount(process.env.PRIVATE_KEY);
            this.web3.eth.accounts.wallet.add(this.account);
        }
    }

    async deployToken(tokenConfig) {
        if (!this.account) {
            throw new Error('No account configured. Please set PRIVATE_KEY in .env');
        }

        console.log('🚀 Deploying ERC-20 Token...');
        console.log('Token Name:', tokenConfig.name);
        console.log('Token Symbol:', tokenConfig.symbol);
        console.log('Decimals:', tokenConfig.decimals);
        console.log('Initial Supply:', tokenConfig.initialSupply);
        console.log('From Account:', this.account.address);

        // Create contract instance
        const contract = new this.web3.eth.Contract(TOKEN_ABI);
        
        // Prepare deployment transaction
        const deployTx = contract.deploy({
            data: TOKEN_BYTECODE,
            arguments: [
                tokenConfig.name,
                tokenConfig.symbol,
                tokenConfig.decimals,
                tokenConfig.initialSupply
            ]
        });

        // Estimate gas
        console.log('\n⛽ Estimating deployment gas...');
        const gasEstimate = await deployTx.estimateGas({
            from: this.account.address
        });
        console.log('Gas Estimate:', gasEstimate);

        // Deploy contract
        console.log('\n📄 Deploying contract...');
        const deployedContract = await deployTx.send({
            from: this.account.address,
            gas: Math.floor(gasEstimate * 1.2), // Add 20% buffer
            gasPrice: process.env.GAS_PRICE || '20000000000'
        });

        console.log('✅ Token deployed successfully!');
        console.log('Contract Address:', deployedContract.options.address);
        console.log('Transaction Hash:', deployedContract.transactionHash);

        return deployedContract;
    }

    async verifyDeployment(contractAddress) {
        console.log('\n🔍 Verifying deployment...');
        
        const contract = new this.web3.eth.Contract(TOKEN_ABI, contractAddress);
        
        try {
            // Get token info
            const tokenInfo = await contract.methods.getTokenInfo().call();
            console.log('Token Info:');
            console.log('  Name:', tokenInfo._name);
            console.log('  Symbol:', tokenInfo._symbol);
            console.log('  Decimals:', tokenInfo._decimals);
            console.log('  Total Supply:', this.web3.utils.fromWei(tokenInfo._totalSupply, 'ether'));
            console.log('  Owner:', tokenInfo._owner);
            console.log('  Paused:', tokenInfo._paused);

            // Check deployer balance
            const balance = await contract.methods.balanceOf(this.account.address).call();
            console.log('  Deployer Balance:', this.web3.utils.fromWei(balance, 'ether'));

            return true;
        } catch (error) {
            console.error('❌ Verification failed:', error.message);
            return false;
        }
    }

    async demonstrateTokenOperations(contractAddress) {
        console.log('\n🧪 Demonstrating token operations...');
        
        const contract = new this.web3.eth.Contract(TOKEN_ABI, contractAddress);
        
        try {
            // Create a test recipient address
            const testRecipient = '0x1234567890123456789012345678901234567890';
            
            // Transfer tokens
            console.log('📤 Transferring tokens to test address...');
            const transferAmount = this.web3.utils.toWei('100', 'ether');
            
            const transferTx = await contract.methods.transfer(testRecipient, transferAmount).send({
                from: this.account.address,
                gas: '100000'
            });
            
            console.log('✅ Transfer successful!');
            console.log('Transaction Hash:', transferTx.transactionHash);
            
            // Check balances
            const senderBalance = await contract.methods.balanceOf(this.account.address).call();
            const recipientBalance = await contract.methods.balanceOf(testRecipient).call();
            
            console.log('📊 Updated Balances:');
            console.log('  Sender:', this.web3.utils.fromWei(senderBalance, 'ether'));
            console.log('  Recipient:', this.web3.utils.fromWei(recipientBalance, 'ether'));
            
            // Demonstrate approval
            console.log('\n✅ Approving spending allowance...');
            const approveAmount = this.web3.utils.toWei('50', 'ether');
            
            const approveTx = await contract.methods.approve(testRecipient, approveAmount).send({
                from: this.account.address,
                gas: '100000'
            });
            
            console.log('✅ Approval successful!');
            console.log('Transaction Hash:', approveTx.transactionHash);
            
            // Check allowance
            const allowance = await contract.methods.allowance(this.account.address, testRecipient).call();
            console.log('📋 Allowance:', this.web3.utils.fromWei(allowance, 'ether'));
            
            // Demonstrate minting (owner only)
            console.log('\n🎯 Minting additional tokens...');
            const mintAmount = this.web3.utils.toWei('1000', 'ether');
            
            const mintTx = await contract.methods.mint(this.account.address, mintAmount).send({
                from: this.account.address,
                gas: '100000'
            });
            
            console.log('✅ Minting successful!');
            console.log('Transaction Hash:', mintTx.transactionHash);
            
            // Check updated total supply
            const totalSupply = await contract.methods.totalSupply().call();
            console.log('📈 New Total Supply:', this.web3.utils.fromWei(totalSupply, 'ether'));
            
        } catch (error) {
            console.error('❌ Token operation failed:', error.message);
        }
    }

    async setupEventListeners(contractAddress) {
        console.log('\n👂 Setting up event listeners...');
        
        const contract = new this.web3.eth.Contract(TOKEN_ABI, contractAddress);
        
        // Listen for Transfer events
        contract.events.Transfer()
            .on('data', (event) => {
                console.log('🔄 Transfer Event:', {
                    from: event.returnValues.from,
                    to: event.returnValues.to,
                    value: this.web3.utils.fromWei(event.returnValues.value, 'ether')
                });
            })
            .on('error', console.error);
        
        // Listen for Approval events
        contract.events.Approval()
            .on('data', (event) => {
                console.log('✅ Approval Event:', {
                    owner: event.returnValues.owner,
                    spender: event.returnValues.spender,
                    value: this.web3.utils.fromWei(event.returnValues.value, 'ether')
                });
            })
            .on('error', console.error);
        
        // Listen for Mint events
        contract.events.Mint()
            .on('data', (event) => {
                console.log('🎯 Mint Event:', {
                    to: event.returnValues.to,
                    amount: this.web3.utils.fromWei(event.returnValues.amount, 'ether')
                });
            })
            .on('error', console.error);
        
        console.log('📡 Event listeners active for 60 seconds...');
        
        // Stop listening after 60 seconds
        setTimeout(() => {
            console.log('⏹️  Stopped event listeners');
            process.exit(0);
        }, 60000);
    }
}

async function deployERC20Token() {
    console.log('🚀 Stellaris ERC-20 Token Deployment');
    console.log('=' * 50);
    
    const deployer = new TokenDeployer();
    
    // Token configuration
    const tokenConfig = {
        name: 'Stellaris Token',
        symbol: 'STK',
        decimals: 18,
        initialSupply: 1000000 // 1 million tokens
    };
    
    try {
        // Deploy token
        const contract = await deployer.deployToken(tokenConfig);
        
        // Verify deployment
        const verified = await deployer.verifyDeployment(contract.options.address);
        
        if (verified) {
            // Demonstrate token operations
            await deployer.demonstrateTokenOperations(contract.options.address);
            
            // Setup event listeners
            await deployer.setupEventListeners(contract.options.address);
        }
        
        console.log('\n🎉 ERC-20 token deployment complete!');
        console.log('Contract Address:', contract.options.address);
        console.log('Save this address to interact with your token later.');
        
    } catch (error) {
        console.error('❌ Deployment failed:', error.message);
        process.exit(1);
    }
}

// Run deployment if this file is executed directly
if (require.main === module) {
    deployERC20Token();
}

module.exports = { TokenDeployer, TOKEN_ABI, TOKEN_BYTECODE };