import React, { useState } from "react";
import { View, ScrollView, TextInput, StyleSheet, Text, Alert, Switch, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { useActiveAccount } from "thirdweb/react";
import { submitKyc } from "../lib/api";
import { Card, H2, Label, Body, GoldButton } from "../components/ui";
import { colors, font } from "../constants/theme";

/**
 * Investor verification. Collects KYC + accreditation info and submits it to the
 * backend, which routes to your licensed transfer agent for approval. Buying
 * unlocks once the agent whitelists the wallet on-chain.
 */
export default function Verify() {
  const account = useActiveAccount();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [country, setCountry] = useState("United States");
  const [accredited, setAccredited] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!account) {
      Alert.alert("Connect first", "Sign in so we can link your verification to your wallet.");
      return;
    }
    if (!name || !email) {
      Alert.alert("Missing info", "Please enter your name and email.");
      return;
    }
    try {
      setBusy(true);
      await submitKyc({
        wallet_address: account.address,
        full_name: name,
        email,
        country,
        accredited,
        accreditation_method: accredited ? "self_attested" : undefined,
      });
      Alert.alert(
        "Submitted for review",
        "Your application has been sent to our transfer agent. You'll be able to invest once it's approved.",
        [{ text: "OK", onPress: () => router.back() }]
      );
    } catch (e: any) {
      Alert.alert("Submission failed", e?.message ?? "Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.hero}>Get verified</Text>
        <Body style={{ marginTop: 8, marginBottom: 18 }}>
          Tokenized real estate is a regulated security. Our licensed transfer agent
          verifies every investor before any purchase.
        </Body>

        <Card>
          <Label>Legal full name</Label>
          <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="Jane Doe" placeholderTextColor={colors.mut} />

          <Label style={{ marginTop: 14 }}>Email</Label>
          <TextInput style={styles.input} value={email} onChangeText={setEmail} placeholder="jane@email.com" autoCapitalize="none" keyboardType="email-address" placeholderTextColor={colors.mut} />

          <Label style={{ marginTop: 14 }}>Country</Label>
          <TextInput style={styles.input} value={country} onChangeText={setCountry} placeholderTextColor={colors.mut} />

          <View style={styles.switchRow}>
            <View style={{ flex: 1, paddingRight: 12 }}>
              <Body style={{ color: colors.cream }}>I am an accredited investor</Body>
              <Label style={{ marginTop: 4 }}>Required for Reg D offerings</Label>
            </View>
            <Switch
              value={accredited}
              onValueChange={setAccredited}
              trackColor={{ true: colors.gold, false: colors.s3 }}
              thumbColor={colors.cream}
            />
          </View>

          {account ? (
            <Label style={{ marginTop: 14 }}>Wallet: {account.address.slice(0, 6)}…{account.address.slice(-4)}</Label>
          ) : (
            <Label style={{ marginTop: 14, color: colors.red }}>Connect your wallet first.</Label>
          )}

          <View style={{ marginTop: 18 }}>
            {busy ? <ActivityIndicator color={colors.gold} /> : <GoldButton label="Submit for review" onPress={submit} />}
          </View>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 48 },
  hero: { color: colors.cream, fontFamily: font.displayItalic, fontStyle: "italic", fontSize: 30 },
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
  switchRow: { flexDirection: "row", alignItems: "center", marginTop: 18 },
});
