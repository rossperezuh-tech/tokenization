// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Snapshot.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title PropertyToken
 * @notice ERC-20 representing fractional ownership of a single commercial
 *         property tokenized through Vesta. The full supply is minted to the
 *         issuer at deploy; tokens are distributed to investors via the
 *         associated PropertySale contract.
 *
 *         Uses ERC20Snapshot so the DistributionVault can pay rental income
 *         pro-rata based on holdings at a frozen point in time (prevents
 *         gaming a distribution by buying right before it).
 */
contract PropertyToken is ERC20Snapshot, Ownable {
    /// @notice Human-readable street address of the underlying property.
    string public propertyAddress;
    /// @notice Property class, e.g. "Multifamily", "Industrial".
    string public propertyType;
    /// @notice Appraised total valuation in whole USD (e.g. 3_250_000).
    uint256 public immutable totalValuationUsd;

    /// @notice Authorized contracts.
    address public saleContract;
    address public distributionVault;

    constructor(
        string memory name_,
        string memory symbol_,
        uint256 maxSupply_,            // 18-decimal supply, e.g. 100_000 * 1e18
        string memory propertyAddress_,
        string memory propertyType_,
        uint256 totalValuationUsd_,
        address issuer_
    ) ERC20(name_, symbol_) {
        propertyAddress = propertyAddress_;
        propertyType = propertyType_;
        totalValuationUsd = totalValuationUsd_;
        _transferOwnership(issuer_);
        _mint(issuer_, maxSupply_);
    }

    function setSaleContract(address sale_) external onlyOwner {
        saleContract = sale_;
    }

    function setDistributionVault(address vault_) external onlyOwner {
        distributionVault = vault_;
    }

    /// @notice Take a balance snapshot. Callable by the issuer or the vault
    ///         (the vault snapshots automatically on each distribution).
    function snapshot() external returns (uint256) {
        require(
            msg.sender == owner() || msg.sender == distributionVault,
            "PropertyToken: not authorized to snapshot"
        );
        return _snapshot();
    }
}
