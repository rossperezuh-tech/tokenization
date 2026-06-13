import React, { useEffect, useState } from "react";
import { View, ScrollView, StyleSheet, Text, Alert, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useActiveAccount, useReadContract } from "thirdweb/react";
import { prepareContractCall, sendTransaction } from "thirdweb";
import { fetchOfferings, type Offering } from "../../lib/api";
import { vaultContract } from "../../lib/contracts";
import { ConnectBar } from "../../components/ConnectBar";
import { Card, H2, Label, Mono, Body, GoldButton } from "../../components/ui";
import { colors, font } from "../../constants/theme";
import { usd, fromUsdc } from "../../lib/format";

export default function Distributions() {
  const account = useActiveAccount();
  const [offerings, setOfferings] = useState<Offering[]>([]);

  useEffect(() => {
    fetchOfferings().then(setOfferings).catch(() => {});
  }, []);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ConnectBar />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.hero}>Distributions</Text>
        <Label style={{ marginBottom: 20 }}>Rental income · claim your share</Label>

        {!account ? (
          <Card>
            <Body>Sign in to view claimable income.</Body>
          </Card>
        ) : offerings.length === 0 ? (
          <ActivityIndicator color={colors.gold} style={{ marginTop: 40 }} />
        ) : (
          offerings
            .filter((o) => o.contracts.distribution_vault)
            .map((o) => <ClaimRow key={o.id} offering={o} owner={account.address} />)
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function ClaimRow({ offering, owner }: { offering: Offering; owner: string }) {
  const account = useActiveAccount();
  const contract = vaultContract(offering.contracts.distribution_vault!);
  const [busy, setBusy] = useState(false);

  const { data: claimable } = useReadContract({
    contract,
    method: "function totalClaimable(address holder) view returns (uint256)",
    params: [owner],
  });

  const amount = claimable ? fromUsdc(claimable as bigint) : 0;
  if (amount <= 0) return null;

  async function claimAll() {
    if (!account) return;
    try {
      setBusy(true);
      const tx = prepareContractCall({ contract, method: "function claimAll()", params: [] });
      await sendTransaction({ transaction: tx, account });
      Alert.alert("Claimed", `Income from ${offering.name} sent to your wallet.`);
    } catch (e: any) {
      Alert.alert("Claim failed", e?.message ?? "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card style={{ marginBottom: 14 }}>
      <View style={styles.row}>
        <View style={{ flex: 1 }}>
          <H2>{offering.name}</H2>
          <Label style={{ marginTop: 4 }}>{offering.symbol} · claimable now</Label>
        </View>
        <Mono style={{ fontSize: 22, color: colors.green }}>{usd(amount, 2)}</Mono>
      </View>
      <View style={{ marginTop: 14 }}>
        {busy ? <ActivityIndicator color={colors.gold} /> : <GoldButton label="Claim income" onPress={claimAll} />}
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 40 },
  hero: { color: colors.cream, fontFamily: font.displayItalic, fontStyle: "italic", fontSize: 34 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
});
