import React, { useEffect, useState, useCallback } from "react";
import { View, ScrollView, RefreshControl, ActivityIndicator, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { fetchOfferings, type Offering } from "../../lib/api";
import { OfferingCard } from "../../components/OfferingCard";
import { ConnectBar } from "../../components/ConnectBar";
import { Body, Label } from "../../components/ui";
import { colors, font } from "../../constants/theme";
import { Text } from "react-native";

export default function Marketplace() {
  const [offerings, setOfferings] = useState<Offering[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      setOfferings(await fetchOfferings());
    } catch (e: any) {
      setError(e?.message ?? "Failed to load offerings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ConnectBar />
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.gold} />}
      >
        <Text style={styles.hero}>Offerings</Text>
        <Label style={{ marginBottom: 20 }}>Tokenized commercial real estate · open to invest</Label>

        {loading && offerings.length === 0 && (
          <ActivityIndicator color={colors.gold} style={{ marginTop: 40 }} />
        )}

        {error && (
          <View style={styles.notice}>
            <Body>Couldn't reach the offerings API.</Body>
            <Label style={{ marginTop: 6 }}>{error}</Label>
          </View>
        )}

        {!loading && offerings.length === 0 && !error && (
          <View style={styles.notice}>
            <Body>No live offerings yet.</Body>
            <Label style={{ marginTop: 6 }}>
              Publish a deal at the Token Offering stage from the Vesta pipeline.
            </Label>
          </View>
        )}

        {offerings.map((o) => (
          <OfferingCard key={o.id} offering={o} />
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 40 },
  hero: { color: colors.cream, fontFamily: font.displayItalic, fontStyle: "italic", fontSize: 34 },
  notice: {
    backgroundColor: colors.s1,
    borderColor: colors.line2,
    borderWidth: 1,
    borderRadius: 12,
    padding: 20,
    marginTop: 12,
  },
});
