/**
 * Deploys a full property offering: PropertyToken + PropertySale + DistributionVault,
 * wires them together, and stocks the sale with inventory.
 *
 * Configure the offering with env vars (see .env.example) or edit OFFERING below.
 *
 * On Base mainnet, set USDC_ADDRESS to the canonical USDC:
 *   0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
 * On testnet/local, leave it empty and a MockUSDC is deployed automatically.
 */
const hre = require("hardhat");

const OFFERING = {
  name: process.env.PROP_NAME || "182 Atlantic Ave",
  symbol: process.env.PROP_SYMBOL || "VATL",
  // total token supply (whole tokens; scaled to 18dp below)
  totalTokens: BigInt(process.env.PROP_TOTAL_TOKENS || "100000"),
  propertyAddress: process.env.PROP_ADDRESS || "182 Atlantic Ave, Brooklyn, NY 11201",
  propertyType: process.env.PROP_TYPE || "Mixed-Use",
  valuationUsd: BigInt(process.env.PROP_VALUATION_USD || "3250000"),
  // USDC (6dp) price per 1 token. e.g. $3.25M / 100k tokens = $32.50 => 32_500000
  pricePerTokenUsdc: BigInt(process.env.PROP_PRICE_USDC || "32500000"),
  // how many tokens to load into the sale contract for investors (rest stays with issuer)
  saleInventoryTokens: BigInt(process.env.PROP_SALE_TOKENS || "70000"),
};

async function main() {
  const [issuer] = await hre.ethers.getSigners();
  console.log("Deployer / issuer:", issuer.address);

  // 1. USDC
  let usdcAddress = process.env.USDC_ADDRESS;
  if (!usdcAddress) {
    const MockUSDC = await hre.ethers.getContractFactory("MockUSDC");
    const usdc = await MockUSDC.deploy();
    await usdc.waitForDeployment();
    usdcAddress = await usdc.getAddress();
    console.log("MockUSDC deployed:", usdcAddress);
  } else {
    console.log("Using existing USDC:", usdcAddress);
  }

  // 2. ComplianceRegistry — controlled by your licensed transfer agent.
  //    AGENT_ADDRESS defaults to the deployer; set it to your TA's wallet.
  const agent = process.env.AGENT_ADDRESS || issuer.address;
  const ComplianceRegistry = await hre.ethers.getContractFactory("ComplianceRegistry");
  const registry = await ComplianceRegistry.deploy(issuer.address, agent);
  await registry.waitForDeployment();
  const registryAddress = await registry.getAddress();
  console.log("ComplianceRegistry deployed:", registryAddress, "(agent:", agent + ")");

  const supply = OFFERING.totalTokens * 10n ** 18n;

  // 3. PropertyToken
  const PropertyToken = await hre.ethers.getContractFactory("PropertyToken");
  const token = await PropertyToken.deploy(
    OFFERING.name, OFFERING.symbol, supply,
    OFFERING.propertyAddress, OFFERING.propertyType, OFFERING.valuationUsd,
    issuer.address
  );
  await token.waitForDeployment();
  const tokenAddress = await token.getAddress();
  console.log("PropertyToken deployed:", tokenAddress);

  // 3. PropertySale
  const PropertySale = await hre.ethers.getContractFactory("PropertySale");
  const sale = await PropertySale.deploy(
    tokenAddress, usdcAddress, OFFERING.pricePerTokenUsdc, issuer.address
  );
  await sale.waitForDeployment();
  const saleAddress = await sale.getAddress();
  console.log("PropertySale deployed:", saleAddress);

  // 4. DistributionVault
  const DistributionVault = await hre.ethers.getContractFactory("DistributionVault");
  const vault = await DistributionVault.deploy(tokenAddress, usdcAddress, issuer.address);
  await vault.waitForDeployment();
  const vaultAddress = await vault.getAddress();
  console.log("DistributionVault deployed:", vaultAddress);

  // 6. SecondaryMarket — P2P order book for the token
  const SecondaryMarket = await hre.ethers.getContractFactory("SecondaryMarket");
  const market = await SecondaryMarket.deploy(
    tokenAddress, usdcAddress, registryAddress, issuer.address
  );
  await market.waitForDeployment();
  const marketAddress = await market.getAddress();
  console.log("SecondaryMarket deployed:", marketAddress);

  // 7. Wire everything
  await (await token.setSaleContract(saleAddress)).wait();
  await (await token.setDistributionVault(vaultAddress)).wait();
  await (await token.setRegistry(registryAddress)).wait();
  await (await sale.setRegistry(registryAddress)).wait();

  // Whitelist the issuer + sale + market so inventory and escrow can move.
  // (Investors get whitelisted by the transfer agent as they pass KYC.)
  await (await registry.setWhitelisted(issuer.address, true)).wait();
  await (await registry.setWhitelisted(saleAddress, true)).wait();
  await (await registry.setWhitelisted(marketAddress, true)).wait();

  const inventory = OFFERING.saleInventoryTokens * 10n ** 18n;
  await (await token.transfer(saleAddress, inventory)).wait();
  console.log(`Loaded ${OFFERING.saleInventoryTokens} tokens into the sale.`);

  console.log("\n=== Deployment summary ===");
  console.log(JSON.stringify({
    network: hre.network.name,
    usdc: usdcAddress,
    complianceRegistry: registryAddress,
    transferAgent: agent,
    propertyToken: tokenAddress,
    propertySale: saleAddress,
    distributionVault: vaultAddress,
    secondaryMarket: marketAddress,
    pricePerTokenUsdc: OFFERING.pricePerTokenUsdc.toString(),
    name: OFFERING.name,
    symbol: OFFERING.symbol,
  }, null, 2));
  console.log("\nAdd these addresses to investor-app/.env and your backend offering record.");
}

main().catch((e) => { console.error(e); process.exitCode = 1; });
