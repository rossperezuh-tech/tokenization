import React, { useCallback, useEffect, useState } from "react";
import { View, ScrollView, TextInput, StyleSheet, Text, ActivityIndicator, Alert, Linking, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, router, useFocusEffect } from "expo-router";
import { useActiveAccount, useReadContract, useSendTransaction } from "thirdweb/react";
import { prepareContractCall, sendTransaction } from "thirdweb";
import {
  fetchOffering, fetchKycStatus, fetchOfferingDocuments, fetchSubscriptionStatus, documentUrl,
  type Offering, type KycStatus, type DataRoomDoc,
} from "../../lib/api";
import { saleContract, usdcContract } from "../../lib/contracts";
import { USDC_ADDRESS } from "../../lib/thirdweb";
import { Card, H2, Label, Mono, Body, Pill, GoldButton, Progress } from "../../components/ui";
import { ConnectBar } from "../../components/ConnectBar";
import { colors, font } from "../../constants/theme";
import { usd, usdCompact, pct, fromTokens, toTokens, toUsdc } from "../../lib/format";

export default function PropertyDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const account = useActiveAccount();
  const [offering, setOffering] = useState<Offering | null>(null);
  const [qty, setQty] = useState("10");
  const [busy, setBusy] = useState(false);
  const [kyc, setKyc] = useState<KycStatus | null>(null);
  const [docs, setDocs] = useState<DataRoomDoc[]>([]);
  const [subscribed, setSubscribed] = useState(false);

  useEffect(() => {
    fetchOffering(Number(id)).then(setOffering).catch(() => setOffering(null));
    fetchOfferingDocuments(Number(id)).then(setDocs).catch(() => setDocs([]));
  }, [id]);

  // Re-check KYC + subscription whenever the screen regains focus (e.g. after
  // returning from the verify or subscribe flows).
  useFocusEffect(
    useCallback(() => {
      if (!account) {
        setKyc(null);
        setSubscribed(false);
        return;
      }
      fetchKycStatus(account.address).then(setKyc).catch(() => setKyc(null));
      fetchSubscriptionStatus(Number(id), account.address)
        .then((s) => setSubscribed(s.signed))
        .catch(() => setSubscribed(false));
    }, [account, id])
  );

  const saleAddr = offering?.contracts.sale ?? undefined;
  const contract = saleAddr ? saleContract(saleAddr) : undefined;

  const { data: sold } = useReadContract({
    contract: contract!,
    method: "function tokensSold() view returns (uint256)",
    queryOptions: { enabled: !!contract },
  });

  if (!offering) {
    return (
      <SafeAreaView style={styles.safe}>
        <ActivityIndicator color={colors.gold} style={{ marginTop: 80 }} />
      </SafeAreaView>
    );
  }

  const p = offering.property;
  const price = offering.token_price_usdc ?? 0;
  const tokens = Math.max(0, parseInt(qty || "0", 10) || 0);
  const cost = tokens * price;
  const soldNum = sold ? fromTokens(sold as bigint) : 0;
  const total = offering.sale_tokens ?? 0;
  const raisePct = total > 0 ? (soldNum / total) * 100 : 0;

  async function handleBuy() {
    if (!account) {
      Alert.alert("Connect first", "Sign in to invest before buying tokens.");
      return;
    }
    if (kyc && !kyc.can_invest) {
      Alert.alert("Verification required", "Complete investor verification before buying.");
      router.push("/verify");
      return;
    }
    if (!subscribed) {
      Alert.alert("Subscription required", "Review and sign the subscription agreement first.");
      router.push(`/subscribe/${id}?tokens=${tokens}`);
      return;
    }
    if (!contract || !saleAddr || !USDC_ADDRESS) {
      Alert.alert("Not available", "This offering isn't fully on-chain yet.");
      return;
    }
    if (tokens <= 0) return;

    try {
      setBusy(true);
      const usdc = usdcContract(USDC_ADDRESS);

      // 1) Approve USDC for the sale contract
      const approveTx = prepareContractCall({
        contract: usdc,
        method: "function approve(address spender, uint256 amount) returns (bool)",
        params: [saleAddr, toUsdc(cost)],
      });
      await sendTransaction({ transaction: approveTx, account });

      // 2) Buy tokens
      const buyTx = prepareContractCall({
        contract,
        method: "function buy(uint256 tokenAmount)",
        params: [toTokens(tokens)],
      });
      await sendTransaction({ transaction: buyTx, account });

      Alert.alert("Purchase complete", `You bought ${tokens} ${offering.symbol ?? "tokens"}.`);
    } catch (e: any) {
      Alert.alert("Transaction failed", e?.message ?? "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe} edges={["bottom"]}>
      <ConnectBar />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.hero}>{offering.name}</Text>
        <Label style={{ marginTop: 6 }}>
          {[p.city, p.state].filter(Boolean).join(", ")} · {p.property_type ?? "—"}
        </Label>
        <View style={{ flexDirection: "row", gap: 8, marginTop: 12 }}>
          <Pill tone="green">{pct(offering.projected_yield)} projected yield</Pill>
          {p.cap_rate ? <Pill tone="muted">{pct(p.cap_rate)} cap rate</Pill> : null}
        </View>

        {offering.summary ? <Body style={{ marginTop: 18 }}>{offering.summary}</Body> : null}

        {/* Key facts */}
        <Card style={{ marginTop: 18 }}>
          <Fact label="Token price" value={usd(price, 2)} />
          <Fact label="Tokens offered" value={total.toLocaleString()} />
          <Fact label="Target raise" value={usdCompact(offering.target_raise_usd)} />
          <Fact label="Property valuation" value={usdCompact(p.asking_price)} />
          {p.sqft ? <Fact label="Size" value={`${p.sqft.toLocaleString()} sqft`} /> : null}
          <View style={{ marginTop: 12 }}>
            <View style={styles.row}>
              <Label>{raisePct.toFixed(0)}% subscribed</Label>
              <Mono style={{ fontSize: 11, color: colors.mid }}>
                {soldNum.toLocaleString()} / {total.toLocaleString()}
              </Mono>
            </View>
            <Progress value={raisePct} />
          </View>
        </Card>

        {/* Data room */}
        {docs.length > 0 && (
          <Card style={{ marginTop: 18 }}>
            <H2>Data room</H2>
            <Label style={{ marginTop: 4, marginBottom: 8 }}>Offering documents</Label>
            {docs.map((d) => (
              <Pressable
                key={d.id}
                onPress={() => Linking.openURL(documentUrl(d))}
                style={({ pressed }) => [styles.docRow, pressed && { opacity: 0.7 }]}
              >
                <Text style={styles.docIcon}>▤</Text>
                <View style={{ flex: 1 }}>
                  <Body style={{ color: colors.cream }}>{d.title}</Body>
                  <Label style={{ marginTop: 2 }}>{d.doc_type.toUpperCase()} · {d.filename}</Label>
                </View>
                <Text style={{ color: colors.gold2, fontSize: 16 }}>↓</Text>
              </Pressable>
            ))}
          </Card>
        )}

        {/* Buy ticket */}
        <Card style={{ marginTop: 18 }}>
          <H2>Invest</H2>
          <Label style={{ marginTop: 10 }}>Number of tokens</Label>
          <TextInput
            value={qty}
            onChangeText={setQty}
            keyboardType="number-pad"
            style={styles.input}
            placeholder="10"
            placeholderTextColor={colors.mut}
          />
          <View style={[styles.row, { marginTop: 16, marginBottom: 16 }]}>
            <Label>Total cost</Label>
            <Mono style={{ fontSize: 22 }}>{usd(cost, 2)}</Mono>
          </View>
          {busy ? (
            <ActivityIndicator color={colors.gold} />
          ) : !account ? (
            <GoldButton label="Sign in to invest" onPress={handleBuy} disabled={tokens <= 0} />
          ) : kyc && kyc.can_invest && subscribed ? (
            <GoldButton label={`Buy ${tokens} tokens`} onPress={handleBuy} disabled={tokens <= 0} />
          ) : kyc && kyc.can_invest ? (
            <GoldButton
              label="Review & sign subscription agreement"
              onPress={() => router.push(`/subscribe/${id}?tokens=${tokens}`)}
              disabled={tokens <= 0}
            />
          ) : (
            <GoldButton
              label={
                kyc?.kyc_status === "pending"
                  ? "Verification under review"
                  : "Get verified to invest"
              }
              onPress={() => router.push("/verify")}
              disabled={kyc?.kyc_status === "pending"}
            />
          )}

          {account && kyc && !kyc.can_invest ? (
            <Label style={{ marginTop: 12, textAlign: "center", color: colors.gold2 }}>
              {kyc.kyc_status === "pending"
                ? "Your verification is with our transfer agent."
                : kyc.kyc_status === "rejected"
                ? "Your application was not approved — contact support."
                : "Investing requires identity + accreditation verification."}
            </Label>
          ) : (
            <Label style={{ marginTop: 12, textAlign: "center" }}>
              Paid in USDC on {offering.chain}. Two steps: approve, then buy.
            </Label>
          )}
        </Card>

        {/* Secondary market */}
        {offering.contracts.secondary_market && (
          <Card style={{ marginTop: 18 }}>
            <View style={styles.row}>
              <View style={{ flex: 1 }}>
                <H2>Secondary market</H2>
                <Label style={{ marginTop: 4 }}>Buy from or sell to other investors</Label>
              </View>
              <GoldButton label="Trade" onPress={() => router.push(`/trade/${id}`)} />
            </View>
          </Card>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <View style={[styles.row, { paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: colors.line2 }]}>
      <Label>{label}</Label>
      <Mono style={{ fontSize: 14 }}>{value}</Mono>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 48 },
  hero: { color: colors.cream, fontFamily: font.displayItalic, fontStyle: "italic", fontSize: 30 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  docRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.line2,
  },
  docIcon: { color: colors.gold, fontSize: 16 },
  input: {
    backgroundColor: colors.s2,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: 8,
    color: colors.cream,
    fontFamily: font.mono,
    fontSize: 20,
    padding: 14,
    marginTop: 6,
  },
});
