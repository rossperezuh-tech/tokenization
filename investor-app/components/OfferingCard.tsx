import React from "react";
import { View, Pressable, StyleSheet } from "react-native";
import { useReadContract } from "thirdweb/react";
import { Link } from "expo-router";
import type { Offering } from "../lib/api";
import { Card, H2, Label, Mono, Pill, Progress } from "./ui";
import { colors, font } from "../constants/theme";
import { saleContract } from "../lib/contracts";
import { usd, usdCompact, pct, fromTokens } from "../lib/format";

/**
 * One property offering. Reads live sold/available figures straight from the
 * sale contract when a sale address is present, falling back to catalogue
 * numbers from the backend.
 */
export function OfferingCard({ offering }: { offering: Offering }) {
  const saleAddr = offering.contracts.sale ?? undefined;
  const contract = saleAddr ? saleContract(saleAddr) : undefined;

  const { data: tokensSold } = useReadContract({
    contract: contract!,
    method: "function tokensSold() view returns (uint256)",
    queryOptions: { enabled: !!contract },
  });

  const sold = tokensSold ? fromTokens(tokensSold as bigint) : 0;
  const total = offering.sale_tokens ?? 0;
  const raisePct = total > 0 ? (sold / total) * 100 : 0;
  const p = offering.property;

  return (
    <Link href={`/property/${offering.id}`} asChild>
      <Pressable>
        <Card style={{ marginBottom: 16 }}>
          <View style={styles.top}>
            <View style={{ flex: 1 }}>
              <H2>{offering.name}</H2>
              <Label style={{ marginTop: 4 }}>
                {[p.city, p.state].filter(Boolean).join(", ")} · {p.property_type ?? "—"}
              </Label>
            </View>
            <Pill tone="green">{pct(offering.projected_yield)} yield</Pill>
          </View>

          <View style={styles.stats}>
            <Stat label="Token price" value={usd(offering.token_price_usdc, 2)} />
            <Stat label="Target raise" value={usdCompact(offering.target_raise_usd)} />
            <Stat label="Valuation" value={usdCompact(p.asking_price)} />
          </View>

          <View style={{ marginTop: 14 }}>
            <View style={styles.progressRow}>
              <Label>{raisePct.toFixed(0)}% subscribed</Label>
              <Mono style={{ fontSize: 11, color: colors.mid }}>
                {sold.toLocaleString()} / {total.toLocaleString()} tokens
              </Mono>
            </View>
            <Progress value={raisePct} />
          </View>
        </Card>
      </Pressable>
    </Link>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={{ flex: 1 }}>
      <Label>{label}</Label>
      <Mono style={{ fontSize: 17, marginTop: 4 }}>{value}</Mono>
    </View>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: "row", alignItems: "flex-start", gap: 12 },
  stats: { flexDirection: "row", gap: 12, marginTop: 16 },
  progressRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 8 },
});
