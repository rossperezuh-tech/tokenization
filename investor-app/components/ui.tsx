import React from "react";
import { View, Text, StyleSheet, ViewStyle, TextStyle, Pressable } from "react-native";
import { colors, font, radius } from "../constants/theme";

export function Card({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function H2({ children, style }: { children: React.ReactNode; style?: TextStyle }) {
  return <Text style={[styles.h2, style]}>{children}</Text>;
}

export function Label({ children, style }: { children: React.ReactNode; style?: TextStyle }) {
  return <Text style={[styles.label, style]}>{children}</Text>;
}

export function Mono({ children, style }: { children: React.ReactNode; style?: TextStyle }) {
  return <Text style={[styles.mono, style]}>{children}</Text>;
}

export function Body({ children, style }: { children: React.ReactNode; style?: TextStyle }) {
  return <Text style={[styles.body, style]}>{children}</Text>;
}

export function Pill({
  children,
  tone = "gold",
}: {
  children: React.ReactNode;
  tone?: "gold" | "green" | "red" | "muted";
}) {
  const map = {
    gold: { bg: colors.goldDim, fg: colors.gold2 },
    green: { bg: colors.greenDim, fg: colors.green },
    red: { bg: colors.redDim, fg: colors.red },
    muted: { bg: colors.s3, fg: colors.mid },
  }[tone];
  return (
    <View style={[styles.pill, { backgroundColor: map.bg }]}>
      <Text style={[styles.pillText, { color: map.fg }]}>{children}</Text>
    </View>
  );
}

export function GoldButton({
  label,
  onPress,
  disabled,
}: {
  label: string;
  onPress?: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.btn,
        disabled && { opacity: 0.4 },
        pressed && !disabled && { opacity: 0.85 },
      ]}
    >
      <Text style={styles.btnText}>{label}</Text>
    </Pressable>
  );
}

/** Thin progress bar (raise progress, lock-up, etc.) */
export function Progress({ value }: { value: number }) {
  return (
    <View style={styles.track}>
      <View style={[styles.fill, { width: `${Math.min(100, Math.max(0, value))}%` }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.s1,
    borderColor: colors.line2,
    borderWidth: 1,
    borderRadius: radius.xl,
    padding: 18,
  },
  h2: { color: colors.cream, fontFamily: font.displayItalic, fontSize: 22, fontStyle: "italic" },
  label: {
    color: colors.mut,
    fontFamily: font.mono,
    fontSize: 9.5,
    letterSpacing: 1.6,
    textTransform: "uppercase",
  },
  mono: { color: colors.cream, fontFamily: font.mono, fontVariant: ["tabular-nums"] },
  body: { color: colors.mid, fontFamily: font.sans, fontSize: 14, lineHeight: 21 },
  pill: { alignSelf: "flex-start", paddingHorizontal: 9, paddingVertical: 4, borderRadius: radius.sm },
  pillText: { fontFamily: font.mono, fontSize: 11 },
  btn: {
    backgroundColor: colors.gold,
    borderRadius: radius.md,
    paddingVertical: 14,
    alignItems: "center",
  },
  btnText: { color: colors.bg, fontFamily: font.sansMed, fontSize: 15, letterSpacing: 0.3 },
  track: { height: 5, borderRadius: 3, backgroundColor: colors.s3, overflow: "hidden" },
  fill: { height: "100%", borderRadius: 3, backgroundColor: colors.gold },
});
