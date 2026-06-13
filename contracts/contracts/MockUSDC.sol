// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/**
 * @title MockUSDC
 * @notice 6-decimal test stablecoin for local/testnet use. On Base mainnet you
 *         would point the sale/vault at the real USDC contract instead.
 */
contract MockUSDC is ERC20 {
    constructor() ERC20("Mock USD Coin", "USDC") {
        _mint(msg.sender, 10_000_000 * 1e6);
    }

    function decimals() public pure override returns (uint8) {
        return 6;
    }

    /// @notice Freely mintable in tests / on testnet.
    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}
