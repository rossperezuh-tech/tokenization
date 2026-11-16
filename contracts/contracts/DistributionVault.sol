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
 *
 *         EXCLUDED HOLDERS. Some addresses hold tokens that belong to nobody
 *         who could ever claim: the sale contract's unsold inventory and the
 *         secondary market's escrow. If their balances counted toward the
 *         payout base, that share of every distribution would be locked in
 *         this vault forever (with 70% of supply still unsold, 70% of the rent
 *         would be stranded). Excluded addresses are therefore removed from the
 *         base, so each distribution is split only among holders who can claim.
 *         A seller's tokens sitting in a market listing at snapshot time do not
 *         earn that distribution — cancel the listing first to be counted.
 */
contract DistributionVault is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    IPropertyTokenSnapshot public immutable token;
    IERC20 public immutable payment; // USDC

    uint256 public constant MAX_EXCLUDED = 8;

    struct Distribution {
        uint256 snapshotId;
        uint256 amount;     // total USDC for this distribution
        uint256 supplyAt;   // ELIGIBLE supply at snapshot (total minus excluded)
        uint256 timestamp;
    }

    Distribution[] public distributions;
    // distributionIndex => holder => claimed?
    mapping(uint256 => mapping(address => bool)) public claimed;

    address[] public excluded;
    // distributionIndex => holder => was excluded when that distribution opened
    mapping(uint256 => mapping(address => bool)) public excludedAt;

    event Distributed(uint256 indexed index, uint256 snapshotId, uint256 amount, uint256 eligibleSupply);
    event Claimed(address indexed holder, uint256 indexed index, uint256 amount);
    event ExcludedSet(address indexed account, bool excluded);

    constructor(address token_, address payment_, address issuer_) {
        token = IPropertyTokenSnapshot(token_);
        payment = IERC20(payment_);
        _transferOwnership(issuer_);
    }

    // ── exclusions ───────────────────────────────────────────────────────
    function isExcluded(address account) public view returns (bool) {
        for (uint256 i = 0; i < excluded.length; i++) {
            if (excluded[i] == account) return true;
        }
        return false;
    }

    function excludedCount() external view returns (uint256) {
        return excluded.length;
    }

    /// @notice Add or remove an address from the payout base. Applies to
    ///         distributions opened AFTER the change; past ones are unaffected.
    function setExcluded(address account, bool status) external onlyOwner {
        require(account != address(0), "DistributionVault: zero address");
        bool current = isExcluded(account);
        if (status && !current) {
            require(excluded.length < MAX_EXCLUDED, "DistributionVault: too many excluded");
            excluded.push(account);
        } else if (!status && current) {
            for (uint256 i = 0; i < excluded.length; i++) {
                if (excluded[i] == account) {
                    excluded[i] = excluded[excluded.length - 1];
                    excluded.pop();
                    break;
                }
            }
        }
        emit ExcludedSet(account, status);
    }

    // ── distribute ───────────────────────────────────────────────────────
    /**
     * @notice Deposit `amount` USDC and open a new distribution.
     * @dev Caller must approve this contract for `amount` USDC first.
     *      The PropertyToken's `distributionVault` must be set to this address
     *      so the snapshot call is authorized.
     */
    function distribute(uint256 amount) external onlyOwner nonReentrant returns (uint256 index) {
        require(amount > 0, "DistributionVault: zero amount");

        uint256 snapId = token.snapshot();
        uint256 eligible = token.totalSupplyAt(snapId);
        index = distributions.length;
        for (uint256 i = 0; i < excluded.length; i++) {
            eligible -= token.balanceOfAt(excluded[i], snapId);
            excludedAt[index][excluded[i]] = true;
        }
        require(eligible > 0, "DistributionVault: no eligible holders");

        distributions.push(Distribution(snapId, amount, eligible, block.timestamp));
        payment.safeTransferFrom(msg.sender, address(this), amount);
        emit Distributed(index, snapId, amount, eligible);
    }

    // ── claim ────────────────────────────────────────────────────────────
    /// @notice USDC claimable by `holder` for distribution `index`.
    function claimable(uint256 index, address holder) public view returns (uint256) {
        if (index >= distributions.length || claimed[index][holder] || excludedAt[index][holder]) return 0;
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

    function _claim(uint256 index) internal returns (uint256 amount) {
        amount = claimable(index, msg.sender);
        if (amount > 0) {
            claimed[index][msg.sender] = true;
            payment.safeTransfer(msg.sender, amount);
            emit Claimed(msg.sender, index, amount);
        }
    }

    function claim(uint256 index) external nonReentrant {
        require(_claim(index) > 0, "DistributionVault: nothing to claim");
    }

    function claimAll() external nonReentrant {
        for (uint256 i = 0; i < distributions.length; i++) {
            _claim(i);
        }
    }

    /// @notice Claim a chosen set of distributions — use this if `claimAll`
    ///         ever becomes too large for one transaction.
    function claimMany(uint256[] calldata indexes) external nonReentrant {
        for (uint256 i = 0; i < indexes.length; i++) {
            _claim(indexes[i]);
        }
    }

    function distributionsCount() external view returns (uint256) {
        return distributions.length;
    }
}
