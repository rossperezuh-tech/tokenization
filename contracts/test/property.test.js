const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Vesta property offering", function () {
  let usdc, registry, token, sale, vault, issuer, agent, alice, bob;
  const SUPPLY = ethers.parseUnits("100000", 18);      // 100k tokens
  const SALE_INV = ethers.parseUnits("70000", 18);     // 70k for sale
  const PRICE = 32_500000n;                            // $32.50 (6dp) per token

  beforeEach(async () => {
    [issuer, agent, alice, bob] = await ethers.getSigners();

    usdc = await (await ethers.getContractFactory("MockUSDC")).deploy();
    registry = await (await ethers.getContractFactory("ComplianceRegistry")).deploy(
      issuer.address, agent.address
    );
    token = await (await ethers.getContractFactory("PropertyToken")).deploy(
      "182 Atlantic Ave", "VATL", SUPPLY,
      "182 Atlantic Ave, Brooklyn, NY", "Mixed-Use", 3_250_000n, issuer.address
    );
    sale = await (await ethers.getContractFactory("PropertySale")).deploy(
      await token.getAddress(), await usdc.getAddress(), PRICE, issuer.address
    );
    vault = await (await ethers.getContractFactory("DistributionVault")).deploy(
      await token.getAddress(), await usdc.getAddress(), issuer.address
    );

    await token.setSaleContract(await sale.getAddress());
    await token.setDistributionVault(await vault.getAddress());
    await token.setRegistry(await registry.getAddress());
    await sale.setRegistry(await registry.getAddress());

    // transfer agent whitelists issuer + sale so inventory can move
    await registry.connect(agent).setWhitelisted(issuer.address, true);
    await registry.connect(agent).setWhitelisted(await sale.getAddress(), true);
    await token.transfer(await sale.getAddress(), SALE_INV);

    // fund investors with USDC
    await usdc.mint(alice.address, 1_000_000n * 1_000000n);
    await usdc.mint(bob.address, 1_000_000n * 1_000000n);
  });

  async function approveInvestors() {
    await registry.connect(agent).setWhitelisted(alice.address, true);
    await registry.connect(agent).setWhitelisted(bob.address, true);
  }

  it("sells tokens for USDC at the set price", async () => {
    await approveInvestors();
    const amount = ethers.parseUnits("100", 18); // buy 100 tokens
    const cost = await sale.cost(amount);
    expect(cost).to.equal(100n * PRICE); // 100 * $32.50 = $3,250

    await usdc.connect(alice).approve(await sale.getAddress(), cost);
    await sale.connect(alice).buy(amount);

    expect(await token.balanceOf(alice.address)).to.equal(amount);
    expect(await sale.tokensSold()).to.equal(amount);
    expect(await sale.totalRaised()).to.equal(cost);
  });

  it("only lets transfer-agent-approved investors buy", async () => {
    const amount = ethers.parseUnits("10", 18);
    const cost = await sale.cost(amount);
    await usdc.connect(alice).approve(await sale.getAddress(), cost);

    // not whitelisted yet
    await expect(sale.connect(alice).buy(amount)).to.be.revertedWith(
      "PropertySale: investor not KYC-approved"
    );

    // transfer agent approves alice
    await registry.connect(agent).setWhitelisted(alice.address, true);
    await sale.connect(alice).buy(amount);
    expect(await token.balanceOf(alice.address)).to.equal(amount);
  });

  it("restricts secondary transfers to whitelisted holders and honors lock-ups", async () => {
    await approveInvestors();
    const amount = ethers.parseUnits("50", 18);
    await usdc.connect(alice).approve(await sale.getAddress(), await sale.cost(amount));
    await sale.connect(alice).buy(amount);

    const [, , , , carol] = await ethers.getSigners();
    // carol not whitelisted -> transfer blocked
    await expect(
      token.connect(alice).transfer(carol.address, amount)
    ).to.be.revertedWith("PropertyToken: transfer not permitted by compliance");

    // bob is whitelisted -> transfer allowed
    await token.connect(alice).transfer(bob.address, amount);
    expect(await token.balanceOf(bob.address)).to.equal(amount);

    // lock bob up -> bob can't send onward until it expires
    const future = Math.floor(Date.now() / 1000) + 3600;
    await registry.connect(agent).setLockup(bob.address, future);
    await expect(
      token.connect(bob).transfer(alice.address, amount)
    ).to.be.revertedWith("PropertyToken: transfer not permitted by compliance");
  });

  it("distributes rental income pro-rata via snapshots", async () => {
    await approveInvestors();
    // Alice buys 300, Bob buys 100 => 75% / 25% of the 400 circulating
    const aliceAmt = ethers.parseUnits("300", 18);
    const bobAmt = ethers.parseUnits("100", 18);
    await usdc.connect(alice).approve(await sale.getAddress(), await sale.cost(aliceAmt));
    await sale.connect(alice).buy(aliceAmt);
    await usdc.connect(bob).approve(await sale.getAddress(), await sale.cost(bobAmt));
    await sale.connect(bob).buy(bobAmt);

    // Issuer distributes $10,000 of rent. Note: total supply includes the
    // issuer's unsold tokens, so holders get their share of the FULL supply.
    const income = 10_000n * 1_000000n;
    await usdc.approve(await vault.getAddress(), income);
    await vault.distribute(income);

    // Alice's share = 300 / 100000 total supply * 10000 = $30
    const aliceClaim = await vault.claimable(0, alice.address);
    expect(aliceClaim).to.equal((aliceAmt * income) / SUPPLY);

    const before = await usdc.balanceOf(alice.address);
    await vault.connect(alice).claim(0);
    const after = await usdc.balanceOf(alice.address);
    expect(after - before).to.equal(aliceClaim);

    // double-claim reverts
    await expect(vault.connect(alice).claim(0)).to.be.revertedWith("DistributionVault: nothing to claim");
  });

  it("secondary market: list, partial fill with fee, cancel, KYC gates", async () => {
    await approveInvestors();
    const market = await (await ethers.getContractFactory("SecondaryMarket")).deploy(
      await token.getAddress(), await usdc.getAddress(),
      await registry.getAddress(), issuer.address
    );
    const marketAddr = await market.getAddress();
    await registry.connect(agent).setWhitelisted(marketAddr, true);
    await market.setFee(50, issuer.address); // 0.50%

    // Alice buys 200 on primary, then lists 100 at $40
    const bought = ethers.parseUnits("200", 18);
    await usdc.connect(alice).approve(await sale.getAddress(), await sale.cost(bought));
    await sale.connect(alice).buy(bought);

    const listAmt = ethers.parseUnits("100", 18);
    const askPrice = 40_000000n; // $40.00
    await token.connect(alice).approve(marketAddr, listAmt);
    await market.connect(alice).list(listAmt, askPrice);
    expect(await token.balanceOf(marketAddr)).to.equal(listAmt); // escrowed

    // Bob partially fills 60 tokens: $2,400 gross, $12 fee (0.5%)
    const fillAmt = ethers.parseUnits("60", 18);
    const gross = 60n * askPrice;
    const fee = (gross * 50n) / 10_000n;
    await usdc.connect(bob).approve(marketAddr, gross);
    const sellerBefore = await usdc.balanceOf(alice.address);
    await market.connect(bob).fill(0, fillAmt);
    expect(await token.balanceOf(bob.address)).to.equal(fillAmt);
    expect((await usdc.balanceOf(alice.address)) - sellerBefore).to.equal(gross - fee);

    // Non-whitelisted buyer is blocked
    const [, , , , mallory] = await ethers.getSigners();
    await usdc.mint(mallory.address, 1_000_000n * 1_000000n);
    await usdc.connect(mallory).approve(marketAddr, gross);
    await expect(market.connect(mallory).fill(0, ethers.parseUnits("1", 18)))
      .to.be.revertedWith("SecondaryMarket: buyer not KYC-approved");

    // Alice cancels the remaining 40 and gets them back
    const aliceTokBefore = await token.balanceOf(alice.address);
    await market.connect(alice).cancel(0);
    expect((await token.balanceOf(alice.address)) - aliceTokBefore)
      .to.equal(ethers.parseUnits("40", 18));
  });

  it("blocks buying more than the sale inventory", async () => {
    await approveInvestors();
    const tooMuch = SALE_INV + ethers.parseUnits("1", 18);
    const cost = await sale.cost(tooMuch);
    await usdc.connect(alice).approve(await sale.getAddress(), cost);
    await expect(sale.connect(alice).buy(tooMuch)).to.be.revertedWith("PropertySale: sold out");
  });
});
