# Vesta Contracts — on-chain RWA layer

Solidity contracts that turn a Vesta pipeline deal into tradeable property
tokens with on-chain rental-income distributions. Built on OpenZeppelin,
deployed to **Base** (cheap L2 with native USDC).

## Contracts

| Contract | Role |
|---|---|
| `ComplianceRegistry.sol` | Investor allowlist + lock-ups, **controlled by your licensed transfer agent**. The hard enforcement point for who may hold/buy. |
| `PropertyToken.sol` | ERC-20 (with snapshots) representing fractional ownership. Transfers are restricted to whitelisted investors via the registry. |
| `PropertySale.sol` | Primary sale — investors pay USDC, receive tokens at a fixed price. Buying requires registry approval. |
| `DistributionVault.sol` | Issuer deposits USDC rent; holders claim pro-rata by snapshot. |
| `SecondaryMarket.sol` | P2P order book — sellers escrow tokens at an ask price, buyers fill with USDC. Both sides must be registry-whitelisted; optional platform fee (≤5%). |
| `MockUSDC.sol` | 6-decimal test stablecoin for local/testnet. |

## Transfer agent & compliance

Because tokenized real estate is a security, `PropertyToken` is a **restricted
token**: it calls `ComplianceRegistry.canTransfer(from, to)` on every move, so
tokens only travel between investors your transfer agent has whitelisted, and
honors per-investor lock-ups (e.g. the Reg D 506(c) one-year hold).

- The registry has an **`agent`** role — set `AGENT_ADDRESS` at deploy to your
  transfer agent's controller wallet. They call `setWhitelisted` / `setLockup`
  as investors clear KYC/accreditation.
- The backend mirrors KYC status (`/api/investors`) and can optionally push the
  on-chain whitelist itself if the platform holds the agent key — but typically
  the transfer agent owns that key and writes directly.

## Setup

```bash
cd contracts
npm install
cp .env.example .env          # fill in DEPLOYER_PRIVATE_KEY (a fresh wallet)
npm run compile
npm test                      # runs the full buy / KYC / distribute / claim suite
```

## Deploy

Start on testnet:

```bash
# get test ETH from a Base Sepolia faucet for your deployer wallet first
npm run deploy:baseSepolia
```

Configure the offering via env vars (see `.env.example`): name, symbol, total
tokens, price per token in USDC (6dp), valuation, and how many tokens to load
into the sale. The deploy script:

1. deploys (or reuses) USDC,
2. deploys `PropertyToken`, `PropertySale`, `DistributionVault`,
3. wires them together and transfers sale inventory into the sale contract,
4. prints all addresses.

Copy the printed addresses into:
- `investor-app/.env` (so the app reads the right contracts), and
- the backend offering record (`POST /api/offerings`) so the property shows up
  in the marketplace.

For **Base mainnet** set `USDC_ADDRESS=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
in `.env`, then `npm run deploy:base`.

## How a payout works

```
issuer approves USDC to the vault
issuer calls vault.distribute(amount)   → snapshots holders, records the round
holder calls vault.claim(i)             → receives balanceAt(snapshot) / supply * amount
```

## Security & compliance notes

- These are standard patterns but **not audited**. Get an audit before holding
  real funds.
- Tokenized real estate is almost always a **security**. In the US you'll need
  an exemption (Reg D / Reg A+ / Reg S), a transfer agent, and KYC/accreditation.
  `PropertySale.kycRequired` + `setKyc` give you an on-chain allowlist to gate
  buyers to verified investors — wire it to your KYC provider's webhook.
