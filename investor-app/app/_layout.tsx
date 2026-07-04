import React from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { ThirdwebProvider } from "thirdweb/react";
import {
  useFonts as useCormorant,
  CormorantGaramond_500Medium_Italic,
  CormorantGaramond_600SemiBold,
} from "@expo-google-fonts/cormorant-garamond";
import { Outfit_400Regular, Outfit_500Medium } from "@expo-google-fonts/outfit";
import { DMMono_400Regular, DMMono_500Medium } from "@expo-google-fonts/dm-mono";
import { colors } from "../constants/theme";

export default function RootLayout() {
  const [loaded] = useCormorant({
    CormorantGaramond_500Medium_Italic,
    CormorantGaramond_600SemiBold,
    Outfit_400Regular,
    Outfit_500Medium,
    DMMono_400Regular,
    DMMono_500Medium,
  });

  // Render regardless of font load so the app never blocks on fonts.
  return (
    <ThirdwebProvider>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.bg },
          headerTintColor: colors.cream,
          headerTitleStyle: { color: colors.cream },
          contentStyle: { backgroundColor: colors.bg },
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="property/[id]" options={{ title: "", headerTransparent: true }} />
        <Stack.Screen name="verify" options={{ title: "Verification", presentation: "modal" }} />
        <Stack.Screen name="subscribe/[id]" options={{ title: "Subscribe", presentation: "modal" }} />
        <Stack.Screen name="trade/[id]" options={{ title: "Trade" }} />
      </Stack>
    </ThirdwebProvider>
  );
}
