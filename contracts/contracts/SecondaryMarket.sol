// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

interface IRegistryView {
    function isWhitelisted(address investor) external view returns (bool);
}

/**
 * @title SecondaryMarket
 * @notice Peer-to-peer order book for one PropertyToken. Sellers escrow tokens
 *         into an ask listing at a USDC price; buyers fill listings (fully or
 *         partially) with USDC.
 *
 *         Compliance is preserved twice over:
 *           1. This contract checks the ComplianceRegistry on list AND fill, so
 *              only transfer-agent-approved investors can trade.
 *           2. The PropertyToken itself enforces canTransfer on every movement,
 *              so even a bug here cannot move tokens to a non-whitelisted wallet.
 *              (This market contract must itself be whitelisted to hold escrow.)
 *
 *         An optional platform fee (basis points on the USDC amount) accrues to
 *         the issuer's fee recipient.
 */
contract SecondaryMarket is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    IERC20 public immutable token;     // PropertyToken (18dp)
    IERC20 public immutable payment;   // USDC (6dp)
    IRegistryView public registry;

    uint16 public feeBps;              // e.g. 50 = 0.50%
    address public feeRecipient;

    struct Listing {
        address seller;
        uint256 remaining;             // tokens still for sale (18dp)
        uint256 pricePerToken;         // USDC 6dp per 1e18 token
        bool active;
    }

    Listing[] public listings;

    event Listed(uint256 indexed id, address indexed seller, uint256 amount, uint256 pricePerToken);
    event Cancelled(uint256 indexed id);
    event Filled(uint256 indexed id, address indexed buyer, uint256 amount, uint256 costUsdc, uint256 feeUsdc);

    constructor(address token_, address payment_, address registry_, address issuer_) {
        token = IERC20(token_);
        payment = IERC20(payment_);
        registry = IRegistryView(registry_);
        feeRecipient = issuer_;
        _transferOwnership(issuer_);
    }

    // ── admin ──────────────────────────────────────────────────────────
    function setFee(uint16 feeBps_, address recipient_) external onlyOwner {
        require(feeBps_ <= 500, "SecondaryMarket: fee above 5% cap");
        feeBps = feeBps_;
        feeRecipient = recipient_;
    }

    function setRegistry(address registry_) external onlyOwner {
        registry = IRegistryView(registry_);
    }

    // ── views ──────────────────────────────────────────────────────────
    function listingsCount() external view returns (uint256) {
        return listings.length;
    }

    function cost(uint256 id, uint256 amount) public view returns (uint256) {
        return (amount * listings[id].pricePerToken) / 1e18;
    }

    // ── sell side ──────────────────────────────────────────────────────
    /// @notice Escrow `amount` tokens at `pricePerToken` (USDC 6dp per token).
    ///         Caller must approve this contract for `amount` tokens first.
    function list(uint256 amount, uint256 pricePerToken) external nonReentrant returns (uint256 id) {
        require(amount > 0, "SecondaryMarket: zero amount");
        require(pricePerToken > 0, "SecondaryMarket: zero price");
        require(_approved(msg.sender), "SecondaryMarket: seller not KYC-approved");

        token.safeTransferFrom(msg.sender, address(this), amount);
        listings.push(Listing(msg.sender, amount, pricePerToken, true));
        id = listings.length - 1;
        emit Listed(id, msg.sender, amount, pricePerToken);
    }

    /// @notice Cancel a listing and reclaim escrowed tokens.
    function cancel(uint256 id) external nonReentrant {
        Listing storage l = listings[id];
        require(l.active, "SecondaryMarket: not active");
        require(l.seller == msg.sender, "SecondaryMarket: not your listing");
        l.active = false;
        uint256 amount = l.remaining;
        l.remaining = 0;
        token.safeTransfer(msg.sender, amount);
        emit Cancelled(id);
    }

    // ── buy side ───────────────────────────────────────────────────────
    /// @notice Fill `amount` tokens from listing `id`. Caller must approve
    ///         this contract for the USDC cost first.
    function fill(uint256 id, uint256 amount) external nonReentrant {
        Listing storage l = listings[id];
        require(l.active, "SecondaryMarket: not active");
        require(amount > 0 && amount <= l.remaining, "SecondaryMarket: bad amount");
        require(_approved(msg.sender), "SecondaryMarket: buyer not KYC-approved");

        uint256 c = (amount * l.pricePerToken) / 1e18;
        uint256 fee = (c * feeBps) / 10_000;

        l.remaining -= amount;
        if (l.remaining == 0) l.active = false;

        payment.safeTransferFrom(msg.sender, l.seller, c - fee);
        if (fee > 0) payment.safeTransferFrom(msg.sender, feeRecipient, fee);
        token.safeTransfer(msg.sender, amount);

        emit Filled(id, msg.sender, amount, c, fee);
    }

    function _approved(address who) internal view returns (bool) {
        if (address(registry) == address(0)) return true;
        return registry.isWhitelisted(who);
    }
}
