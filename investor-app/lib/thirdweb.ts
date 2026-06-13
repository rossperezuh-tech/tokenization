import { createThirdwebClient } from "thirdweb";
import { base, baseSepolia, type Chain } from "thirdweb/chains";
import { inAppWallet, createWallet } from "thirdweb/wallets";

const clientId = process.env.EXPO_PUBLIC_THIRDWEB_CLIENT_ID;

if (!clientId) {
  console.warn(
    "EXPO_PUBLIC_THIRDWEB_CLIENT_ID is not set — wallet connection will fail. " +
      "Get a free client ID at https://thirdweb.com/dashboard"
  );
}

export const client = createThirdwebClient({ clientId: clientId ?? "MISSING" });

export const activeChain: Chain =
  process.env.EXPO_PUBLIC_CHAIN === "base" ? base : baseSepolia;

export const USDC_ADDRESS = process.env.EXPO_PUBLIC_USDC_ADDRESS ?? "";
export const USDC_DECIMALS = 6;

/**
 * Wallets offered in the connect sheet. The in-app wallet lets non-crypto
 * investors sign in with email / social and get a wallet automatically —
 * critical for "buy from your phone" without MetaMask.
 */
export const wallets = [
  inAppWallet({
    auth: { options: ["email", "google", "apple", "phone"] },
  }),
  createWallet("io.metamask"),
  createWallet("com.coinbase.wallet"),
];
