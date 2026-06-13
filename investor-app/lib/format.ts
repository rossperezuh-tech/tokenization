export const usd = (n: number | null | undefined, dp = 0) =>
  n == null
    ? "—"
    : "$" + n.toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp });

export const usdCompact = (n: number | null | undefined) => {
  if (n == null) return "—";
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

export const pct = (n: number | null | undefined, dp = 1) =>
  n == null ? "—" : `${n.toFixed(dp)}%`;

/** Convert a 6-decimal USDC bigint to a JS number of dollars. */
export const fromUsdc = (v: bigint) => Number(v) / 1e6;
/** Convert dollars to a 6-decimal USDC bigint. */
export const toUsdc = (dollars: number) => BigInt(Math.round(dollars * 1e6));
/** Convert whole tokens to 18-decimal bigint. */
export const toTokens = (whole: number) => BigInt(Math.round(whole * 1e6)) * 10n ** 12n;
/** Convert 18-decimal token bigint to whole-token number. */
export const fromTokens = (v: bigint) => Number(v / 10n ** 12n) / 1e6;
