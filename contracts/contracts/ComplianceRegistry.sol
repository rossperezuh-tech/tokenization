// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title ComplianceRegistry
 * @notice The on-chain investor allowlist controlled by your licensed
 *         TRANSFER AGENT. The transfer agent verifies KYC/AML and accreditation
 *         off-chain, then records the result here by whitelisting the investor's
 *         wallet (and optionally setting a transfer lock-up, e.g. the Reg D
 *         506(c) one-year holding period).
 *
 *         PropertyToken consults this registry on every transfer, so tokens can
 *         only move between approved investors — making them genuine restricted
 *         securities rather than freely tradeable tokens.
 *
 * Roles:
 *   - owner  : the issuer (you). Can set/replace the agent.
 *   - agent  : the transfer agent's controller wallet. Manages the allowlist
 *              and lock-ups. This is the key your TA holds.
 */
contract ComplianceRegistry is Ownable {
    address public agent;

    mapping(address => bool) public whitelisted;
    mapping(address => uint64) public lockupUntil; // unix seconds; sends blocked until then

    event AgentUpdated(address indexed agent);
    event Whitelisted(address indexed investor, bool status);
    event LockupSet(address indexed investor, uint64 until);

    constructor(address issuer_, address agent_) {
        _transferOwnership(issuer_);
        agent = agent_;
        emit AgentUpdated(agent_);
    }

    modifier onlyAgent() {
        require(msg.sender == agent || msg.sender == owner(), "Registry: caller is not the transfer agent");
        _;
    }

    /// @notice Issuer can rotate the transfer agent's controller wallet.
    function setAgent(address agent_) external onlyOwner {
        agent = agent_;
        emit AgentUpdated(agent_);
    }

    // ── allowlist management (transfer agent) ────────────────────────────
    function setWhitelisted(address investor, bool status) public onlyAgent {
        whitelisted[investor] = status;
        emit Whitelisted(investor, status);
    }

    function setWhitelistedBatch(address[] calldata investors, bool status) external onlyAgent {
        for (uint256 i = 0; i < investors.length; i++) {
            whitelisted[investors[i]] = status;
            emit Whitelisted(investors[i], status);
        }
    }

    /// @notice Set a transfer lock-up for an investor (0 = no lock-up).
    function setLockup(address investor, uint64 until) external onlyAgent {
        lockupUntil[investor] = until;
        emit LockupSet(investor, until);
    }

    // ── views used by PropertyToken / PropertySale ───────────────────────
    function isWhitelisted(address investor) external view returns (bool) {
        return whitelisted[investor];
    }

    /// @notice Whether `from` may transfer to `to` right now.
    function canTransfer(address from, address to) external view returns (bool) {
        if (!whitelisted[from] || !whitelisted[to]) return false;
        if (block.timestamp < lockupUntil[from]) return false;
        return true;
    }
}
