# Vesta Invest — investor app (iOS · Android · Web)

A single Expo / Expo Router codebase that runs as a **native mobile app and a
website**, where investors browse tokenized properties and buy tokens on-chain
straight from their phone. Wallet + payments via [thirdweb](https://thirdweb.com);
styled after the Nexus private-bank dashboard.

## Screens

- **Marketplace** — live offerings sourced from the Vesta backend, with real
  subscription progress read from the sale contracts.
- **Property detail** — facts + a buy ticket: enter token count → approve USDC →
  buy. In-app (email/social) wallet means non-crypto investors can buy too.
- **Portfolio** — your token balances and estimated value, read from chain.
- **Distributions** — claimable rental income, with one-tap `claimAll`.

## Setup

```bash
cd investor-app
npm install
cp .env.example .env
```

Fill in `.env`:

| Var | Value |
|---|---|
| `EXPO_PUBLIC_THIRDWEB_CLIENT_ID` | free from thirdweb.com/dashboard |
| `EXPO_PUBLIC_CHAIN` | `base-sepolia` (testnet) or `base` |
| `EXPO_PUBLIC_API_URL` | your running Vesta backend, e.g. `http://localhost:8000` |
| `EXPO_PUBLIC_USDC_ADDRESS` | MockUSDC (testnet) or canonical USDC (mainnet) |

> thirdweb's React Native SDK has a few native peer deps. If `expo start` warns
> about missing modules, run `npx expo install` for the named packages or follow
> thirdweb's React Native setup guide — versions move faster than this template.

## Run

```bash
npm run web       # open in a browser  → the "website"
npm run ios       # iOS simulator
npm run android   # Android emulator
npm start         # then scan the QR with Expo Go on your phone
```

## How it connects to the rest of the system

```
Vesta pipeline (deal hits "Token Offering")
        │  POST /api/offerings  (+ deployed contract addresses)
        ▼
Backend /api/offerings  ──read──▶  this app's Marketplace
        │                                  │ buy / claim
        ▼                                  ▼
   contracts/ (PropertyToken, Sale, DistributionVault on Base)
```

The backend is the **catalogue + economics**; the **contracts are the ledger**.
The app reads offerings from the API and live balances/sales/claims from chain.

## Going to production

- Build with EAS: `eas build` for the app stores; deploy the web export to any
  static host (`npx expo export -p web`).
- Gate buying to KYC'd investors via `PropertySale.setKyc` (see contracts).
- This is an MVP foundation — add per-distribution history, secondary-market
  trading, document vault (K-1s/PPMs), and push notifications next.
