import React from "react";
import { Tabs } from "expo-router";
import { Text } from "react-native";
import { colors, font } from "../../constants/theme";

function Icon({ label, color }: { label: string; color: string }) {
  return <Text style={{ color, fontSize: 18 }}>{label}</Text>;
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerTitleStyle: { color: colors.cream, fontFamily: font.displayItalic, fontSize: 22 },
        tabBarStyle: {
          backgroundColor: colors.s1,
          borderTopColor: colors.line2,
          height: 64,
          paddingBottom: 8,
          paddingTop: 8,
        },
        tabBarActiveTintColor: colors.gold2,
        tabBarInactiveTintColor: colors.mut,
        tabBarLabelStyle: { fontFamily: font.mono, fontSize: 10, letterSpacing: 1 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Marketplace",
          tabBarLabel: "MARKET",
          tabBarIcon: ({ color }) => <Icon label="◈" color={color} />,
        }}
      />
      <Tabs.Screen
        name="portfolio"
        options={{
          title: "Portfolio",
          tabBarLabel: "PORTFOLIO",
          tabBarIcon: ({ color }) => <Icon label="▦" color={color} />,
        }}
      />
      <Tabs.Screen
        name="distributions"
        options={{
          title: "Distributions",
          tabBarLabel: "INCOME",
          tabBarIcon: ({ color }) => <Icon label="❖" color={color} />,
        }}
      />
    </Tabs>
  );
}
