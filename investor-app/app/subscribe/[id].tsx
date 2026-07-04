import React, { useEffect, useState } from "react";
import { View, ScrollView, TextInput, StyleSheet, Text, Alert, Switch, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, router } from "expo-router";
import { useActiveAccount } from "thirdweb/react";
import { fetchAgreement, signSubscription, type AgreementPreview } from "../../lib/api";
import { Card, Label, Body, GoldButton, Mono } from "../../components/ui";
import { colors, font } from "../../constants/theme";
import { usd } from "../../lib/format";

/**
 * Subscription agreement review + e-sign. The investor reviews the exact
 * generated agreement text, types their legal name, and consents — the signed
 * document's hash is stored server-side. Buying unlocks once signed.
 */
export default function Subscribe() {
  const { id, tokens: tokensParam } = useLocalSearchParams<{ id: string; tokens?: string }>();
  const account = useActiveAccount();
  const offeringId = Number(id);
  const tokens = Math.max(1, parseInt(tokensParam ?? "10", 10) || 10);

  const [name, setName] = useState("");
  const [agreement, setAgreement] = useState<AgreementPreview | null>(null);
  const [consent, setConsent] = useState(false);
  const [signature, setSignature] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (account && name.trim().length > 2) {
      const t = setTimeout(() => {
        fetchAgreement(offeringId, account.address, name.trim(), tokens)
          .then(setAgreement)
          .catch(() => setAgreement(null));
      }, 500);
      return () => clearTimeout(t);
    }
  }, [account, name, offeringId, tokens]);

  async function sign() {
    if (!account || !agreement) return;
    if (signature.trim().toLowerCase() !== name.trim().toLowerCase()) {
      Alert.alert("Signature mismatch", "Your typed signature must match your legal name exactly.");
      return;
    }
    try {
      setBusy(true);
      await signSubscription({
        offering_id: offeringId,
        wallet_address: account.address,
        investor_name: name.trim(),
        token_amount: tokens,
        signature_name: signature.trim(),
        consent,
        agreement_sha256: agreement.sha256,
      });
      Alert.alert("Agreement signed", "Your subscription is recorded. You can now complete your purchase.", [
        { text: "Continue", onPress: () => router.back() },
      ]);
    } catch (e: any) {
      Alert.alert("Signing failed", e?.message ?? "Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.hero}>Subscription agreement</Text>
        <Body style={{ marginTop: 8, marginBottom: 16 }}>
          Review the agreement for your purchase of {tokens.toLocaleString()} tokens, then sign
          electronically.
        </Body>

        <Card>
          <Label>Your legal full name</Label>
          <TextInput
            style={styles.input}
            value={name}
            onChangeText={setName}
            placeholder="Jane Doe"
            placeholderTextColor={colors.mut}
          />
        </Card>

        {agreement && (
          <>
            <Card style={{ marginTop: 14, maxHeight: 320 }}>
              <ScrollView nestedScrollEnabled>
                <Mono style={{ fontSize: 11, lineHeight: 17, color: colors.mid }}>{agreement.text}</Mono>
              </ScrollView>
            </Card>
            <Card style={{ marginTop: 14 }}>
              <View style={styles.row}>
                <Label>Total subscription</Label>
                <Mono style={{ fontSize: 20 }}>{usd(agreement.usd_amount, 2)}</Mono>
              </View>
              <View style={[styles.row, { marginTop: 14 }]}>
                <Body style={{ flex: 1, paddingRight: 12, color: colors.cream }}>
                  I consent to sign this agreement electronically.
                </Body>
                <Switch
                  value={consent}
                  onValueChange={setConsent}
                  trackColor={{ true: colors.gold, false: colors.s3 }}
                  thumbColor={colors.cream}
                />
              </View>
              <Label style={{ marginTop: 14 }}>Type your name to sign</Label>
              <TextInput
                style={[styles.input, { fontFamily: font.displayItalic, fontStyle: "italic", fontSize: 19 }]}
                value={signature}
                onChangeText={setSignature}
                placeholder={name || "Jane Doe"}
                placeholderTextColor={colors.mut}
              />
              <View style={{ marginTop: 16 }}>
                {busy ? (
                  <ActivityIndicator color={colors.gold} />
                ) : (
                  <GoldButton label="Sign agreement" onPress={sign} disabled={!consent || !signature.trim()} />
                )}
              </View>
              <Label style={{ marginTop: 10, textAlign: "center" }}>
                Document hash {agreement.sha256.slice(0, 12)}… is recorded with your signature.
              </Label>
            </Card>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 48 },
  hero: { color: colors.cream, fontFamily: font.displayItalic, fontStyle: "italic", fontSize: 28 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  input: {
    backgroundColor: colors.s2,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: 8,
    color: colors.cream,
    fontFamily: font.sans,
    fontSize: 15,
    padding: 13,
    marginTop: 6,
  },
});
