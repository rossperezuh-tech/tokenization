/**
 * Reads live offerings from the Vesta backend (FastAPI /api/offerings).
 * On-chain numbers (sold, available, balances) are read directly from the
 * contracts in the screens; this is the property catalogue + economics.
 */
const BASE = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export type Offering = {
  id: number;
  lead_id: number;
  name: string;
  symbol: string | null;
  summary: string | null;
  image_url: string | null;
  chain: string;
  contracts: {
    token: string | null;
    sale: string | null;
    distribution_vault: string | null;
    usdc: string | null;
  };
  total_tokens: number | null;
  sale_tokens: number | null;
  token_price_usdc: number | null;
  target_raise_usd: number | null;
  projected_yield: number | null;
  status: string;
  is_live: boolean;
  property: {
    address: string | null;
    city: string | null;
    state: string | null;
    property_type: string | null;
    asking_price: number | null;
    cap_rate: number | null;
    sqft: number | null;
    latitude: number | null;
    longitude: number | null;
    score: number | null;
  };
};

export async function fetchOfferings(): Promise<Offering[]> {
  const res = await fetch(`${BASE}/api/offerings/?live_only=true`);
  if (!res.ok) throw new Error(`Offerings request failed: ${res.status}`);
  const data = await res.json();
  return data.offerings as Offering[];
}

export async function fetchOffering(id: number): Promise<Offering> {
  const res = await fetch(`${BASE}/api/offerings/${id}`);
  if (!res.ok) throw new Error(`Offering ${id} not found`);
  return (await res.json()) as Offering;
}
