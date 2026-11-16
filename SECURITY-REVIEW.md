# Security & code review — November 2026

Scope: backend API, smart contracts, investor website, operator dashboard,
investor app. Everything below marked **Fixed** is on the
`claude/security-review-fixes` branch with a test that demonstrates it.

## Fixed

### Backend
| Severity | Problem | Fix |
|---|---|---|
| High | Anyone could list another investor's private documents (K-1s) by knowing their wallet address | Requires a wallet-signature session for that wallet |
| High | Anyone could file or overwrite a KYC application, or e-sign a subscription agreement, for a wallet they don't control | Same wallet-signature session |
| High | Investor could tick "accredited" and, once KYC was approved, be treated as accredited without the transfer agent verifying it | Self-attestation stored separately; only the transfer agent's flag unlocks investing; approved records can't be self-edited |
| High | Public status endpoints returned name, email and country for any wallet | Gate flags only |
| Medium | CORS allowed every origin with credentials | Allow-list via `ALLOWED_ORIGINS` |
| Medium | Session signing key had a known default | Random per-process fallback; set `JWT_SECRET` |
| Medium | No limit on login attempts | Throttled after repeated failures |
| Medium | Uploads had no type or size limit and trusted the browser's content type | Extension allow-list, size cap, forced attachment download |
| Medium | Draft offerings and their documents were publicly readable | Live offerings only |
| Low | Transfer-agent secret compared with `!=` | Constant-time comparison |
| Bug | `/health` returned 404 (shadowed by static mount) | Route order fixed |
| Bug | Scraper IDs used `hash()`, which changes every process — duplicates on every run | SHA-256 |
| Bug | Price-drop email re-sent every historical drop daily | Only drops since last check |
| Bug | `python-multipart` missing — app could not start | Added |
| Bug | SQLite only — data lost on any cloud redeploy | `DATABASE_URL` (Postgres) support |
| Risk | Outreach email sent from a hard-coded domain you may not own | Sender must be configured (`OUTREACH_FROM_EMAIL`) |
| Risk | Inbound email template claimed a track record ("we've helped many owners") | Removed |

### Smart contracts
| Severity | Problem | Fix |
|---|---|---|
| High | Rent distributions were split across **total** supply, including unsold tokens held by the sale contract and tokens in market escrow. With 70% unsold, 70% of every payout would be locked in the vault permanently | Excluded holders are removed from the payout base |
| High | Deploy script would deploy a freely mintable test stablecoin on mainnet if `USDC_ADDRESS` was unset — anyone could mint it and buy the whole offering | Refuses on Base mainnet |
| Medium | Costs rounded down: dust-sized purchases were free; sellers short-changed on fractional fills | Round up |
| Low | `claimAll` re-entered a guarded function | Restructured; added `claimMany` |

### Investor website
| Severity | Problem | Fix |
|---|---|---|
| High | Stored XSS: offering names/addresses (which originate from the public seller form and scraped listings) were written into the page unescaped, on a page where wallets connect | All dynamic values escaped |
| Medium | Wallet library loaded from a third-party CDN with no integrity check | Served from this site |
| Risk | Sample portfolio figures and a "KYC verified · accredited" label displayed as if real | Labelled as preview; label removed |

### Apps
| Problem | Fix |
|---|---|
| Property, trade and offering-card screens crashed on first load (contract read hook given an undefined contract) | Placeholder contract while loading |
| App sent `buy` before the USDC approval was mined, so purchases would revert | Waits for confirmation; approval amount read from the contract |
| Operator dashboard could only call `/api` on its own host — cannot work on Vercel | `VITE_API_URL` |
| Stale compiled dashboard committed to the repo | Removed; build output ignored |

## Not fixed — decide before going live

1. **Contracts are unaudited and owned by a single key.** The owner can clear
   the compliance registry, change price mid-sale, and withdraw proceeds. Use a
   multisig (e.g. Safe) as owner and get an independent audit before mainnet.
2. **Reg D holding period is manual.** The one-year lock-up is only enforced if
   the transfer agent sets it per investor after each purchase.
3. **Operator login is one shared password**, token kept in browser storage, no
   second factor. Fine for one operator on testnet; not for a team.
4. **No database migrations.** Tables are created on first start only; a schema
   change on a live database needs a migration tool (Alembic).
5. **Uploaded documents live on local disk.** On Railway that needs a
   persistent volume or object storage, or they vanish on redeploy.
6. **Personal data is stored unencrypted** in the application database. Prefer
   to let the transfer agent / KYC vendor hold identity data and store only
   their reference ID.
7. **Wallet sign-in supports standard wallets only**, not smart-contract
   accounts (EIP-1271).
8. **Outreach templates make specific promises** (close in 21 days, no
   contingencies, capital from accredited investors). Have counsel review —
   publicly describing an offering has consequences for which Reg D exemption
   you can use.
9. **Scrapers** are untested against the live sites and both sites prohibit
   scraping in their terms.
10. **The investor app has not been run on a device.** It type-checks; the
    on-chain flows need a testnet walkthrough.
11. **Repository visibility.** If the repo is still public, make it private.

## How to re-run the checks

```bash
# contracts
cd contracts && npm install && npx hardhat test

# dashboard
cd frontend && npm install && npm run build
```
