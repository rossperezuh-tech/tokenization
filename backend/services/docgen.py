"""
Document generation for the data room.

Generates the subscription agreement text for an offering + investor. The
investor e-signs the exact generated text; we store its SHA-256 so the signed
version is verifiable later.

IMPORTANT: this template is a structural placeholder. Securities counsel must
review/replace the language before any real offering.
"""

import hashlib
from datetime import datetime

from models.database import TokenOffering


def _usd(n) -> str:
    return f"${n:,.2f}" if n is not None else "$—"


def generate_subscription_agreement(
    offering: TokenOffering,
    investor_name: str,
    wallet_address: str,
    token_amount: float,
) -> dict:
    lead = offering.lead
    prop_address = ", ".join(
        filter(None, [lead.address if lead else offering.name,
                      lead.city if lead else None,
                      lead.state if lead else None])
    )
    price = offering.token_price_usdc or 0.0
    usd_amount = token_amount * price
    today = datetime.utcnow().strftime("%B %d, %Y")

    text = f"""SUBSCRIPTION AGREEMENT
{offering.name} ({offering.symbol or "—"})
Dated: {today}

[TEMPLATE — FOR STRUCTURE ONLY. SECURITIES COUNSEL MUST REVIEW AND REPLACE
THIS LANGUAGE BEFORE ANY OFFERING IS MADE TO INVESTORS.]

1. SUBSCRIPTION. The undersigned ("Investor") irrevocably subscribes for
   {token_amount:,.0f} tokens of {offering.symbol or offering.name} at
   {_usd(price)} per token, for a total subscription amount of
   {_usd(usd_amount)}, representing fractional economic interests in the
   property located at {prop_address} (the "Property"), issued by
   [ISSUER LLC NAME] (the "Issuer").

2. INVESTOR. Name: {investor_name}
   Wallet address of record: {wallet_address}

3. ACCREDITATION. Investor represents that Investor is an "accredited
   investor" as defined in Rule 501(a) of Regulation D under the Securities
   Act of 1933, and that Investor's status has been verified by the Issuer's
   transfer agent.

4. RESTRICTED SECURITIES. Investor understands the tokens are securities that
   have not been registered under the Securities Act, are subject to transfer
   restrictions enforced on-chain by the Issuer's compliance registry, and may
   be subject to lock-up periods.

5. RISKS. Investor acknowledges receipt of the offering materials in the data
   room, including the Private Placement Memorandum, and understands that an
   investment in the Property involves substantial risk, including total loss.

6. DISTRIBUTIONS. Rental income distributions, if any, are paid in USDC
   pro-rata to token holders of record at each distribution snapshot.

7. ELECTRONIC SIGNATURE. Investor consents to conduct this transaction
   electronically. Typing Investor's legal name below and submitting
   constitutes Investor's electronic signature under the U.S. E-SIGN Act.

Accepted and agreed as of the date first written above.
"""

    sha = hashlib.sha256(text.encode()).hexdigest()
    return {
        "text": text,
        "sha256": sha,
        "token_amount": token_amount,
        "usd_amount": usd_amount,
    }
