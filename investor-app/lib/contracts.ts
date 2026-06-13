import { getContract } from "thirdweb";
import { client, activeChain } from "./thirdweb";

/**
 * Minimal human-readable ABIs for the three Vesta contracts. thirdweb accepts
 * Solidity function signatures directly in prepareContractCall / useReadContract,
 * so we only need these for typed getContract usage.
 */
export const SALE_ABI = [
  "function buy(uint256 tokenAmount)",
  "function cost(uint256 tokenAmount) view returns (uint256)",
  "function pricePerToken() view returns (uint256)",
  "function tokensSold() view returns (uint256)",
  "function totalRaised() view returns (uint256)",
  "function available() view returns (uint256)",
  "function kycRequired() view returns (bool)",
  "function kycApproved(address) view returns (bool)",
] as const;

export const TOKEN_ABI = [
  "function balanceOf(address) view returns (uint256)",
  "function totalSupply() view returns (uint256)",
  "function symbol() view returns (string)",
  "function propertyAddress() view returns (string)",
  "function propertyType() view returns (string)",
  "function totalValuationUsd() view returns (uint256)",
] as const;

export const VAULT_ABI = [
  "function distribute(uint256 amount) returns (uint256)",
  "function claim(uint256 index)",
  "function claimAll()",
  "function claimable(uint256 index, address holder) view returns (uint256)",
  "function totalClaimable(address holder) view returns (uint256)",
  "function distributionsCount() view returns (uint256)",
] as const;

export const ERC20_ABI = [
  "function approve(address spender, uint256 amount) returns (bool)",
  "function allowance(address owner, address spender) view returns (uint256)",
  "function balanceOf(address) view returns (uint256)",
  "function decimals() view returns (uint8)",
] as const;

export function tokenContract(address: string) {
  return getContract({ client, chain: activeChain, address });
}
export function saleContract(address: string) {
  return getContract({ client, chain: activeChain, address });
}
export function vaultContract(address: string) {
  return getContract({ client, chain: activeChain, address });
}
export function usdcContract(address: string) {
  return getContract({ client, chain: activeChain, address });
}
