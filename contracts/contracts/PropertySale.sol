// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title PropertySale
 * @notice Primary sale for a PropertyToken. Investors pay USDC and receive
 *         property tokens at a fixed price. The sale contract holds an
 *         inventory of tokens (transferred in by the issuer at setup) and
 *         sells from that balance until sold out.
 *
 *         Optional KYC allowlist: when `kycRequired` is true only approved
 *         addresses can buy — important for securities compliance.
 */
contract PropertySale is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    IERC20 public immutable token;     // the PropertyToken (18 decimals)
    IERC20 public immutable payment;   // USDC (6 decimals)

    /// @notice USDC (6dp) charged per 1 whole token (1e18 units).
    uint256 public pricePerToken;
    uint256 public totalRaised;        // USDC, 6dp
    uint256 public tokensSold;         // token units, 18dp

    bool public kycRequired;
    mapping(address => bool) public kycApproved;

    event Purchased(address indexed buyer, uint256 tokenAmount, uint256 costUsdc);
    event KycSet(address indexed investor, bool approved);

    constructor(
        address token_,
        address payment_,
        uint256 pricePerToken_,
        address issuer_
    ) {
        token = IERC20(token_);
        payment = IERC20(payment_);
        pricePerToken = pricePerToken_;
        _transferOwnership(issuer_);
    }

    // ── admin ──────────────────────────────────────────────────────────
    function setPrice(uint256 pricePerToken_) external onlyOwner {
        pricePerToken = pricePerToken_;
    }

    function setKycRequired(bool required_) external onlyOwner {
        kycRequired = required_;
    }

    function setKyc(address investor_, bool approved_) external onlyOwner {
        kycApproved[investor_] = approved_;
        emit KycSet(investor_, approved_);
    }

    function setKycBatch(address[] calldata investors_, bool approved_) external onlyOwner {
        for (uint256 i = 0; i < investors_.length; i++) {
            kycApproved[investors_[i]] = approved_;
            emit KycSet(investors_[i], approved_);
        }
    }

    // ── views ──────────────────────────────────────────────────────────
    /// @notice USDC cost for `tokenAmount` (18dp) tokens.
    function cost(uint256 tokenAmount) public view returns (uint256) {
        return (tokenAmount * pricePerToken) / 1e18;
    }

    /// @notice Tokens still available for sale.
    function available() external view returns (uint256) {
        return token.balanceOf(address(this));
    }

    // ── buy ────────────────────────────────────────────────────────────
    /**
     * @notice Buy `tokenAmount` (18dp) property tokens.
     * @dev Caller must approve this contract to spend `cost(tokenAmount)` USDC first.
     */
    function buy(uint256 tokenAmount) external nonReentrant {
        require(!kycRequired || kycApproved[msg.sender], "PropertySale: KYC required");
        require(tokenAmount > 0, "PropertySale: zero amount");

        uint256 c = cost(tokenAmount);
        require(token.balanceOf(address(this)) >= tokenAmount, "PropertySale: sold out");

        payment.safeTransferFrom(msg.sender, address(this), c);
        token.safeTransfer(msg.sender, tokenAmount);

        totalRaised += c;
        tokensSold += tokenAmount;
        emit Purchased(msg.sender, tokenAmount, c);
    }

    // ── issuer withdrawals ───────────────────────────────────────────────
    function withdrawProceeds(address to) external onlyOwner {
        payment.safeTransfer(to, payment.balanceOf(address(this)));
    }

    function withdrawUnsold(address to) external onlyOwner {
        token.safeTransfer(to, token.balanceOf(address(this)));
    }
}
