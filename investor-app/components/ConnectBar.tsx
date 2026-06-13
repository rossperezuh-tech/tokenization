import React from "react";
import { View } from "react-native";
import { ConnectButton } from "thirdweb/react";
import { client, activeChain, wallets } from "../lib/thirdweb";
import { colors } from "../constants/theme";

/**
 * The wallet connect control. Uses thirdweb's ConnectButton with the in-app
 * (email/social) wallet first so investors can sign in without a crypto wallet.
 */
export function ConnectBar() {
  return (
    <View style={{ alignItems: "flex-end", paddingHorizontal: 16, paddingVertical: 8 }}>
      <ConnectButton
        client={client}
        wallets={wallets}
        chain={activeChain}
        theme="dark"
        connectButton={{ label: "Sign in to invest" }}
        connectModal={{ size: "compact", title: "Vesta Invest" }}
        appMetadata={{ name: "Vesta Invest", url: "https://vesta.capital" }}
      />
    </View>
  );
}
