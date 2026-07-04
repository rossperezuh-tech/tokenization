import React, { useEffect, useState } from "react";
import { View, ScrollView, StyleSheet, Text, ActivityIndicator, Linking, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useActiveAccount, useReadContract } from "thirdweb/react";
import { fetchOfferings, fetchInvestorDocuments, documentUrl, type Offering, type DataRoomDoc } from "../../lib/api";
import { tokenContract } from "../../lib/contracts";
import { ConnectBar } from "../../components/ConnectBar";
import { Card, H2, Label, Mono, Body, Pill } from "../../components/ui";
import { colors, font } from "../../constants/theme";
import { usd, fromTokens } from "../../lib/format";

export default function Portfolio() {
  const account = useActiveAccount();
  const [offerings, setOfferings] = useState<Offering[]>([]);
  const [myDocs, setMyDocs] = useState<DataRoomDoc[]>([]);

  useEffect(() => {
    fetchOfferings().then(setOfferings).catch(() => {});
  }, []);

  useEffect(() => {
    if (account) {
      fetchInvestorDocuments(account.address).then(setMyDocs).catch(() => setMyDocs([]));
    } else {
      setMyDocs([]);
    }
  }, [account]);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ConnectBar />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.hero}>Portfolio</Text>
        <Label style={{ marginBottom: 20 }}>Your tokenized holdings</Label>

        {!account ? (
          <Card>
            <Body>Sign in to view your holdings.</Body>
          </Card>
        ) : offerings.length === 0 ? (
          <ActivityIndicator color={colors.gold} style={{ marginTop: 40 }} />
        ) : (
          offerings
            .filter((o) => o.contracts.token)
            .map((o) => <Holding key={o.id} offering={o} owner={account.address} />)
        )}

        {account && myDocs.length > 0 && (
          <Card style={{ marginTop: 10 }}>
            <H2>Your documents</H2>
            <Label style={{ marginTop: 4, marginBottom: 8 }}>K-1s · signed agreements</Label>
            {myDocs.map((d) => (
              <Pressable
                key={d.id}
                onPress={() => Linking.openURL(documentUrl(d))}
                style={({ pressed }) => [styles.docRow, pressed && { opacity: 0.7 }]}
              >
                <View style={{ flex: 1 }}>
                  <Body style={{ color: colors.cream }}>{d.title}</Body>
                  <Label style={{ marginTop: 2 }}>{d.doc_type.toUpperCase()}</Label>
                </View>
                <Text style={{ color: colors.gold2, fontSize: 16 }}>↓</Text>
              </Pressable>
            ))}
          </Card>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function Holding({ offering, owner }: { offering: Offering; owner: string }) {
  const contract = tokenContract(offering.contracts.token!);
  const { data: bal } = useReadContract({
    contract,
    method: "function balanceOf(address) view returns (uint256)",
    params: [owner],
  });

  const tokens = bal ? fromTokens(bal as bigint) : 0;
  if (tokens <= 0) return null;
  const value = tokens * (offering.token_price_usdc ?? 0);

  return (
    <Card style={{ marginBottom: 14 }}>
      <View style={styles.row}>
        <View style={{ flex: 1 }}>
          <H2>{offering.name}</H2>
          <Label style={{ marginTop: 4 }}>
            {offering.symbol} · {offering.property.property_type ?? "—"}
          </Label>
        </View>
        <Pill tone="green">{offering.projected_yield?.toFixed(1) ?? "—"}%</Pill>
      </View>
      <View style={[styles.row, { marginTop: 14 }]}>
        <View>
          <Label>Tokens</Label>
          <Mono style={{ fontSize: 17, marginTop: 3 }}>{tokens.toLocaleString()}</Mono>
        </View>
        <View style={{ alignItems: "flex-end" }}>
          <Label>Est. value</Label>
          <Mono style={{ fontSize: 17, marginTop: 3 }}>{usd(value)}</Mono>
        </View>
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 40 },
  hero: { color: colors.cream, fontFamily: font.displayItalic, fontStyle: "italic", fontSize: 34 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  docRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.line2,
  },
});
