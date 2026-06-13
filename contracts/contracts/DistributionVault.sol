// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

interface IPropertyTokenSnapshot {
    function snapshot() external returns (uint256);
    function balanceOfAt(address account, uint256 snapshotId) external view returns (uint256);
    function totalSupplyAt(uint256 snapshotId) external view returns (uint256);
}

/**
 * @title DistributionVault
 * @notice Pays rental income to PropertyToken holders pro-rata. The issuer
 *         deposits USDC and calls `distribute`, which freezes a balance
 *         snapshot. Holders then `claim` their share of each distribution
 *         based on what they held at that snapshot.
 *
 *         Snapshot-based (pull) accounting means a holder cannot buy right
 *         before a payout to capture it, and claims are gas-paid by the
 *         claimer rather than the issuer pushing to everyone.
 */
contract DistributionVault is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    IPropertyTokenSnapshot public immutable token;
    IERC20 public immutable payment; // USDC

    struct Distribution {
        uint256 snapshotId;
        uint256 amount;     // total USDC for this distribution
        uint256 supplyAt;   // token total supply at snapshot
        uint256 timestamp;
    }

    Distribution[] public distributions;
    // distributionIndex => holder => claimed?
    mapping(uint256 => mapping(address => bool)) public claimed;

    event Distributed(uint256 indexed index, uint256 snapshotId, uint256 amount);
    event Claimed(address indexed holder, uint256 indexed index, uint256 amount);

    constructor(address token_, address payment_, address issuer_) {
        token = IPropertyTokenSnapshot(token_);
        payment = IERC20(payment_);
        _transferOwnership(issuer_);
    }

    /**
     * @notice Deposit `amount` USDC and open a new distribution.
     * @dev Caller must approve this contract for `amount` USDC first.
     *      The PropertyToken's `distributionVault` must be set to this address
     *      so the snapshot call is authorized.
     */
    function distribute(uint256 amount) external onlyOwner returns (uint256 index) {
        require(amount > 0, "DistributionVault: zero amount");
        payment.safeTransferFrom(msg.sender, address(this), amount);

        uint256 snapId = token.snapshot();
        uint256 supply = token.totalSupplyAt(snapId);
        require(supply > 0, "DistributionVault: no supply");

        distributions.push(Distribution(snapId, amount, supply, block.timestamp));
        index = distributions.length - 1;
        emit Distributed(index, snapId, amount);
    }

    /// @notice USDC claimable by `holder` for distribution `index`.
    function claimable(uint256 index, address holder) public view returns (uint256) {
        if (index >= distributions.length || claimed[index][holder]) return 0;
        Distribution memory d = distributions[index];
        uint256 bal = token.balanceOfAt(holder, d.snapshotId);
        return (bal * d.amount) / d.supplyAt;
    }

    /// @notice Total USDC claimable by `holder` across all distributions.
    function totalClaimable(address holder) external view returns (uint256 total) {
        for (uint256 i = 0; i < distributions.length; i++) {
            total += claimable(i, holder);
        }
    }

    function claim(uint256 index) public nonReentrant {
        uint256 amount = claimable(index, msg.sender);
        require(amount > 0, "DistributionVault: nothing to claim");
        claimed[index][msg.sender] = true;
        payment.safeTransfer(msg.sender, amount);
        emit Claimed(msg.sender, index, amount);
    }

    function claimAll() external {
        for (uint256 i = 0; i < distributions.length; i++) {
            if (claimable(i, msg.sender) > 0) {
                claim(i);
            }
        }
    }

    function distributionsCount() external view returns (uint256) {
        return distributions.length;
    }
}
