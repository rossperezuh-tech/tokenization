/**
 * Investor session.
 *
 * Anything that reads or writes one investor's private data (KYC application,
 * K-1s, subscription signatures) requires proof that the caller controls the
 * wallet. The app proves it by signing a server-issued challenge — a free,
 * off-chain signature, not a transaction — and receives a short-lived token.
 *
 * Tokens are kept in memory only (never written to disk) and cached per wallet
 * so the user is asked to sign at most about once an hour.
 */
import type { Account } from "thirdweb/wallets";

const BASE = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";
const cache = new Map<string, { token: string; expires: number }>();

export async function getInvestorToken(account: Account): Promise<string> {
  const key = account.address.toLowerCase();
  const hit = cache.get(key);
  if (hit && hit.expires > Date.now() + 60_000) return hit.token;

  const chRes = await fetch(`${BASE}/api/auth/wallet/challenge/${account.address}`);
  if (!chRes.ok) throw new Error("Could not start wallet sign-in");
  const challenge = (await chRes.json()) as { message: string; issued_at: number; nonce: string };

  const signature = await account.signMessage({ message: challenge.message });

  const res = await fetch(`${BASE}/api/auth/wallet/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      wallet_address: account.address,
      issued_at: challenge.issued_at,
      nonce: challenge.nonce,
      signature,
    }),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail;
    throw new Error(detail ?? "Wallet sign-in failed");
  }
  const { token } = (await res.json()) as { token: string };
  cache.set(key, { token, expires: Date.now() + 55 * 60 * 1000 });
  return token;
}

export function clearInvestorSession(address?: string) {
  if (address) cache.delete(address.toLowerCase());
  else cache.clear();
}
