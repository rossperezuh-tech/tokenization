const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Vesta property offering", function () {
  let usdc, token, sale, vault, issuer, alice, bob;
  const SUPPLY = ethers.parseUnits("100000", 18);      // 100k tokens
  const SALE_INV = ethers.parseUnits("70000", 18);     // 70k for sale
  const PRICE = 32_500000n;                            // $32.50 (6dp) per token

  beforeEach(async () => {
    [issuer, alice, bob] = await ethers.getSigners();

    usdc = await (await ethers.getContractFactory("MockUSDC")).deploy();
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
    await token.transfer(await sale.getAddress(), SALE_INV);

    // fund investors with USDC
    await usdc.mint(alice.address, 1_000_000n * 1_000000n);
    await usdc.mint(bob.address, 1_000_000n * 1_000000n);
  });

  it("sells tokens for USDC at the set price", async () => {
    const amount = ethers.parseUnits("100", 18); // buy 100 tokens
    const cost = await sale.cost(amount);
    expect(cost).to.equal(100n * PRICE); // 100 * $32.50 = $3,250

    await usdc.connect(alice).approve(await sale.getAddress(), cost);
    await sale.connect(alice).buy(amount);

    expect(await token.balanceOf(alice.address)).to.equal(amount);
    expect(await sale.tokensSold()).to.equal(amount);
    expect(await sale.totalRaised()).to.equal(cost);
  });

  it("enforces KYC when required", async () => {
    await sale.setKycRequired(true);
    const amount = ethers.parseUnits("10", 18);
    const cost = await sale.cost(amount);
    await usdc.connect(alice).approve(await sale.getAddress(), cost);

    await expect(sale.connect(alice).buy(amount)).to.be.revertedWith("PropertySale: KYC required");

    await sale.setKyc(alice.address, true);
    await sale.connect(alice).buy(amount);
    expect(await token.balanceOf(alice.address)).to.equal(amount);
  });

  it("distributes rental income pro-rata via snapshots", async () => {
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

  it("blocks buying more than the sale inventory", async () => {
    const tooMuch = SALE_INV + ethers.parseUnits("1", 18);
    const cost = await sale.cost(tooMuch);
    await usdc.connect(alice).approve(await sale.getAddress(), cost);
    await expect(sale.connect(alice).buy(tooMuch)).to.be.revertedWith("PropertySale: sold out");
  });
});
