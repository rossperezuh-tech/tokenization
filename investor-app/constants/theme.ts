/**
 * Nexus design tokens — a private-bank terminal aesthetic.
 * Dark lacquer, brushed gold, serif headlines, tabular mono figures.
 * Mirrors the reference investor dashboard.
 */
export const colors = {
  bg: "#07080a",
  s1: "#0d1014",
  s2: "#13171d",
  s3: "#1b2028",
  line: "#222831",
  line2: "#1a1f27",
  gold: "#c9a96e",
  gold2: "#e0c48a",
  goldDim: "rgba(201,169,110,0.14)",
  cream: "#eae6dc",
  mid: "#8a8678",
  mut: "#5a5850",
  green: "#4ec98a",
  greenDim: "rgba(78,201,138,0.12)",
  red: "#e06060",
  redDim: "rgba(224,96,96,0.12)",
  blue: "#68a6d2",
};

export const font = {
  // Loaded via expo-font in app/_layout.tsx
  display: "CormorantGaramond_600SemiBold",
  displayItalic: "CormorantGaramond_500Medium_Italic",
  sans: "Outfit_400Regular",
  sansMed: "Outfit_500Medium",
  mono: "DMMono_400Regular",
  monoMed: "DMMono_500Medium",
};

export const radius = { sm: 5, md: 7, lg: 11, xl: 14 };
export const space = (n: number) => n * 4;
