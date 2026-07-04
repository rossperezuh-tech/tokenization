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

// ── KYC / compliance (driven by the licensed transfer agent) ──────────
export type KycStatus = {
  wallet_address: string;
  kyc_status: "not_started" | "pending" | "approved" | "rejected";
  can_invest: boolean;
  full_name?: string;
};

export async function fetchKycStatus(address: string): Promise<KycStatus> {
  const res = await fetch(`${BASE}/api/investors/${address}/status`);
  if (!res.ok) throw new Error(`KYC status request failed: ${res.status}`);
  return (await res.json()) as KycStatus;
}

// ── data room ─────────────────────────────────────────────────────────
export type DataRoomDoc = {
  id: number;
  title: string;
  doc_type: string;
  filename: string;
  download_url: string;
};

export async function fetchOfferingDocuments(offeringId: number): Promise<DataRoomDoc[]> {
  const res = await fetch(`${BASE}/api/documents/offering/${offeringId}`);
  if (!res.ok) return [];
  return (await res.json()).documents as DataRoomDoc[];
}

export async function fetchInvestorDocuments(address: string): Promise<DataRoomDoc[]> {
  const res = await fetch(`${BASE}/api/documents/investor/${address}`);
  if (!res.ok) return [];
  return (await res.json()).documents as DataRoomDoc[];
}

export function documentUrl(doc: DataRoomDoc): string {
  return `${BASE}${doc.download_url}`;
}

// ── subscription e-sign ───────────────────────────────────────────────
export type AgreementPreview = { text: string; sha256: string; usd_amount: number };

export async function fetchAgreement(
  offeringId: number,
  wallet: string,
  name: string,
  tokens: number
): Promise<AgreementPreview> {
  const params = new URLSearchParams({ wallet, name, tokens: String(tokens) });
  const res = await fetch(`${BASE}/api/subscriptions/agreement/${offeringId}?${params}`);
  if (!res.ok) throw new Error(`Agreement preview failed: ${res.status}`);
  return (await res.json()) as AgreementPreview;
}

export async function signSubscription(payload: {
  offering_id: number;
  wallet_address: string;
  investor_name: string;
  investor_email?: string;
  token_amount: number;
  signature_name: string;
  consent: boolean;
  agreement_sha256: string;
}) {
  const res = await fetch(`${BASE}/api/subscriptions/sign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail;
    throw new Error(detail ?? `Sign failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchSubscriptionStatus(
  offeringId: number,
  wallet: string
): Promise<{ signed: boolean }> {
  const res = await fetch(`${BASE}/api/subscriptions/status/${offeringId}/${wallet}`);
  if (!res.ok) return { signed: false };
  return (await res.json()) as { signed: boolean };
}

export async function submitKyc(payload: {
  wallet_address: string;
  full_name: string;
  email: string;
  phone?: string;
  country?: string;
  accredited: boolean;
  accreditation_method?: string;
}): Promise<KycStatus> {
  const res = await fetch(`${BASE}/api/investors/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`KYC submit failed: ${res.status}`);
  return (await res.json()) as KycStatus;
}
