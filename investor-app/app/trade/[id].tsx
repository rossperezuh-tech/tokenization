import React, { useEffect, useState } from "react";
import { View, ScrollView, TextInput, StyleSheet, Text, Alert, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams } from "expo-router";
import { useActiveAccount, useReadContract } from "thirdweb/react";
import { prepareContractCall, sendTransaction, getContract } from "thirdweb";
import { client, activeChain, USDC_ADDRESS } from "../../lib/thirdweb";
import { fetchOffering, type Offering } from "../../lib/api";
import { Card, H2, Label, Mono, Body, GoldButton, Pill } from "../../components/ui";
import { colors, font } from "../../constants/theme";
import { usd, fromTokens, toTokens, toUsdc, fromUsdc } from "../../lib/format";

/**
 * Secondary market for one property token. Whitelisted holders list tokens for
 * sale (escrowed on-chain); other verified investors fill listings with USDC.
 * The ComplianceRegistry gates both sides, so only transfer-agent-approved
 * wallets can trade.
 */
export default function Trade() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const account = useActiveAccount();
  const [offering, setOffering] = useState<Offering | null>(null);
  const [busy, setBusy] = useState(false);
  const [sellAmt, setSellAmt] = useState("10");
  const [sellPrice, setSellPrice] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    fetchOffering(Number(id)).then(setOffering).catch(() => setOffering(null));
  }, [id]);

  const marketAddr = offering?.contracts.secondary_market ?? undefined;
  const tokenAddr = offering?.contracts.token ?? undefined;
  const market = marketAddr ? getContract({ client, chain: activeChain, address: marketAddr }) : undefined;

  const { data: count } = useReadContract({
    contract: market!,
    method: "function listingsCount() view returns (uint256)",
    queryOptions: { enabled: !!market, refetchInterval: 15000 },
  });

  if (!offering) {
    return (
      <SafeAreaView style={styles.safe}>
        <ActivityIndicator color={colors.gold} style={{ marginTop: 80 }} />
      </SafeAreaView>
    );
  }

  if (!marketAddr || !tokenAddr) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={{ padding: 16 }}>
          <Card><Body>Secondary trading isn't enabled for this offering yet.</Body></Card>
        </View>
      </SafeAreaView>
    );
  }

  async function createListing() {
    if (!account || !market) return;
    const amt = parseFloat(sellAmt) || 0;
    const price = parseFloat(sellPrice) || 0;
    if (amt <= 0 || price <= 0) {
      Alert.alert("Invalid listing", "Enter a token amount and ask price.");
      return;
    }
    try {
      setBusy(true);
      const token = getContract({ client, chain: activeChain, address: tokenAddr! });
      const approveTx = prepareContractCall({
        contract: token,
        method: "function approve(address spender, uint256 amount) returns (bool)",
        params: [marketAddr!, toTokens(amt)],
      });
      await sendTransaction({ transaction: approveTx, account });
      const listTx = prepareContractCall({
        contract: market,
        method: "function list(uint256 amount, uint256 pricePerToken) returns (uint256)",
        params: [toTokens(amt), toUsdc(price)],
      });
      await sendTransaction({ transaction: listTx, account });
      Alert.alert("Listed", `${amt} tokens listed at ${usd(price, 2)} each.`);
      setRefreshKey((k) => k + 1);
    } catch (e: any) {
      Alert.alert("Listing failed", e?.message ?? "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const n = count ? Number(count) : 0;

  return (
    <SafeAreaView style={styles.safe} edges={["bottom"]}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.hero}>Trade {offering.symbol}</Text>
        <Label style={{ marginTop: 6 }}>{offering.name} · secondary market</Label>

        {/* Sell */}
        <Card style={{ marginTop: 18 }}>
          <H2>Sell tokens</H2>
          <View style={{ flexDirection: "row", gap: 10, marginTop: 10 }}>
            <View style={{ flex: 1 }}>
              <Label>Amount</Label>
              <TextInput style={styles.input} value={sellAmt} onChangeText={setSellAmt} keyboardType="decimal-pad" placeholderTextColor={colors.mut} />
            </View>
            <View style={{ flex: 1 }}>
              <Label>Ask $ / token</Label>
              <TextInput style={styles.input} value={sellPrice} onChangeText={setSellPrice} keyboardType="decimal-pad" placeholder={String(offering.token_price_usdc ?? "")} placeholderTextColor={colors.mut} />
            </View>
          </View>
          <View style={{ marginTop: 14 }}>
            {busy ? <ActivityIndicator color={colors.gold} /> : (
              <GoldButton label={account ? "List for sale" : "Sign in to trade"} onPress={createListing} disabled={!account} />
            )}
          </View>
          <Label style={{ marginTop: 10, textAlign: "center" }}>
            Tokens are escrowed on-chain until filled or cancelled.
          </Label>
        </Card>

        {/* Order book */}
        <Card style={{ marginTop: 18 }}>
          <H2>Open listings</H2>
          <Label style={{ marginTop: 4, marginBottom: 6 }}>{n} total (filled/cancelled hidden)</Label>
          {n === 0 && <Body>No listings yet — be the first to post an ask.</Body>}
          {Array.from({ length: n }, (_, i) => (
            <ListingRow key={`${i}-${refreshKey}`} market={market!} marketAddr={marketAddr!} index={i}
              symbol={offering.symbol ?? "tokens"} onFilled={() => setRefreshKey((k) => k + 1)} />
          ))}
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

function ListingRow({ market, marketAddr, index, symbol, onFilled }: {
  market: any; marketAddr: string; index: number; symbol: string; onFilled: () => void;
}) {
  const account = useActiveAccount();
  const [busy, setBusy] = useState(false);
  const { data } = useReadContract({
    contract: market,
    method: "function listings(uint256) view returns (address seller, uint256 remaining, uint256 pricePerToken, bool active)",
    params: [BigInt(index)],
  });

  if (!data) return null;
  const [seller, remaining, pricePerToken, active] = data as [string, bigint, bigint, boolean];
  if (!active || remaining === 0n) return null;

  const remainingNum = fromTokens(remaining);
  const priceNum = fromUsdc(pricePerToken);
  const mine = account && seller.toLowerCase() === account.address.toLowerCase();

  async function act() {
    if (!account) return;
    try {
      setBusy(true);
      if (mine) {
        const tx = prepareContractCall({
          contract: market, method: "function cancel(uint256 id)", params: [BigInt(index)],
        });
        await sendTransaction({ transaction: tx, account });
        Alert.alert("Cancelled", "Your tokens were returned.");
      } else {
        const usdc = getContract({ client, chain: activeChain, address: USDC_ADDRESS });
        const cost = (remaining * pricePerToken) / 10n ** 18n;
        const approveTx = prepareContractCall({
          contract: usdc,
          method: "function approve(address spender, uint256 amount) returns (bool)",
          params: [marketAddr, cost],
        });
        await sendTransaction({ transaction: approveTx, account });
        const fillTx = prepareContractCall({
          contract: market, method: "function fill(uint256 id, uint256 amount)",
          params: [BigInt(index), remaining],
        });
        await sendTransaction({ transaction: fillTx, account });
        Alert.alert("Filled", `You bought ${remainingNum.toLocaleString()} ${symbol}.`);
      }
      onFilled();
    } catch (e: any) {
      Alert.alert("Transaction failed", e?.message ?? "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={rowStyles.row}>
      <View style={{ flex: 1 }}>
        <Mono style={{ fontSize: 14 }}>{remainingNum.toLocaleString()} {symbol}</Mono>
        <Label style={{ marginTop: 2 }}>
          @ {usd(priceNum, 2)} · {seller.slice(0, 6)}…{seller.slice(-4)}{mine ? " (you)" : ""}
        </Label>
      </View>
      <Mono style={{ fontSize: 14, color: colors.green, marginRight: 12 }}>{usd(remainingNum * priceNum)}</Mono>
      {busy ? <ActivityIndicator color={colors.gold} /> : (
        <Pill tone={mine ? "muted" : "gold"}>
          <Text onPress={act}>{mine ? "Cancel" : "Buy"}</Text>
        </Pill>
      )}
    </View>
  );
}

const rowStyles = StyleSheet.create({
  row: {
    flexDirection: "row", alignItems: "center", paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: colors.line2,
  },
});

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 48 },
  hero: { color: colors.cream, fontFamily: font.displayItalic, fontStyle: "italic", fontSize: 28 },
  input: {
    backgroundColor: colors.s2, borderColor: colors.line, borderWidth: 1, borderRadius: 8,
    color: colors.cream, fontFamily: font.mono, fontSize: 16, padding: 12, marginTop: 6,
  },
});
