# Bond Valuation Methodology

This note explains how the engine values each bond type, where the numbers in the interface come from, and what the models assume.

## Core principle

A bond is a list of dated cash flows. Its value is the sum of those cash flows, each multiplied by a discount factor:

$$
P = \sum_{i=1}^{n} CF_i \times DF(t_i)
$$

Every bond type in the engine is valued this way. The types differ only in how the cash flows are built. Bonds with embedded options are the one exception. Whether they are redeemed early depends on the path of rates, so they are valued on an interest-rate tree.

## Cash flow schedule

Coupon dates are found by stepping back from the maturity date one coupon period at a time until the settlement date is passed. If the bond matures on the last day of a month, every coupon falls on the last day of its month.

The day count convention measures how much of the current coupon period has elapsed. With $A$ the days from the previous coupon to settlement and $E$ the days in the period, the accrued fraction is $a = A / E$.

| Convention | Days from previous coupon to settlement | Days in the coupon period |
|---|---|---|
| 30/360 | Each month counted as 30 days (US rule, without its end-of-February adjustment) | 360 / coupons per year |
| ACT/ACT | Actual calendar days | Actual calendar days in the period |
| ACT/360 | Actual calendar days | 360 / coupons per year |
| ACT/365 | Actual calendar days | 365 / coupons per year |

With $m$ coupons per year, the $i$-th remaining coupon is paid at time

$$
t_i = \frac{i - a}{m} \text{ years}
$$

Time is counted in coupon periods rather than calendar days. This is the market convention and the one used by the Excel bond functions while more than one coupon remains. In the final coupon period Excel, like the US Treasury market, switches to simple interest. The engine keeps compounding there.

With a fixed-length period (30/360, ACT/360, ACT/365) the days counted can reach or pass the period length just before a coupon date. The engine then keeps one day to the next coupon, so the formula above is not exact on those days.

## Clean price, dirty price and accrued interest

The seller of a bond is owed the interest earned since the last coupon:

$$
AI = a \times \text{next coupon}
$$

The present value of the cash flows is the **dirty price**, the amount actually paid. The quoted **clean price** removes accrued interest so that the price does not jump on coupon dates:

$$
P_{clean} = P_{dirty} - AI
$$

All prices are per 100 of face value. Market value is the dirty price applied to the face value.

## Discounting

The engine offers two discount curves.

### Flat yield

A single yield $y$ discounts every cash flow, compounded $k$ times per year:

$$
DF(t) = \left(1 + \frac{y}{k}\right)^{-k t}
$$

With $k$ equal to the coupon frequency this is the street convention behind quoted yields, apart from the final coupon period noted above. With $k = 1$ the yield is an annual effective rate, which is the convention of the original pricing script this project grew out of. Any spread entered is added to the yield.

### Bootstrapped zero curve

Each cash flow is discounted at the zero rate $z(t)$ for its own maturity plus a constant spread $s$:

$$
DF(t) = \left(1 + z(t) + s\right)^{-t}
$$

Zero rates are annually compounded. Between curve nodes the zero rate is interpolated linearly. Before the first node and after the last it is held flat.

## Yield curve bootstrapping

Zero rates cannot be observed directly at most maturities, because few zero coupon bonds trade. Published curves often give par yields instead, the coupon at which a bond of that maturity would trade at 100. Bootstrapping extracts the zero rates those par yields imply.

Instruments are processed from the shortest maturity to the longest.

**Zero rate.** Used directly as the zero rate at its maturity.

**Par yield.** A bond with coupon $c$ equal to the par yield and maturity $T$ must have a clean price of 100. Its $n$ coupons are counted back from maturity, one every $1/m$ years, at times $t_1, \dots, t_n = T$:

$$
100 + AI = \sum_{i=1}^{n} \frac{100 c}{m} DF(t_i) + 100 DF(T)
$$

$AI$ is the interest accrued when $T$ is not a whole number of coupon periods, $AI = \frac{100 c}{m} (n - m T)$. Otherwise it is zero. With semi-annual coupons this applies to the 1-month and 3-month Treasury yields, which are treated as bonds with one coupon left.

The discount factors up to the previous node are already known. The only unknown is the zero rate at $T$, which also sets the interpolated rates between the previous node and $T$. The engine finds it by bisection: it tries a rate, prices the bond, and halves the search range until the two sides of the equation match.

Bisection is used instead of a closed-form formula because coupon dates rarely line up with the quoted maturities. A 7-year par bond pays coupons at 5.5, 6 and 6.5 years, where no quote exists, so those rates depend on the very number being solved for.

**Forward rate.** The annually compounded rate implied between two nodes $t_1$ and $t_2$:

$$
f(t_1, t_2) = \left(\frac{DF(t_1)}{DF(t_2)}\right)^{\frac{1}{t_2 - t_1}} - 1
$$

### Curve sources

The Yield curve tab takes its quotes from one of three sources.

| Source | Quotes | Treatment |
|---|---|---|
| Fed | US Treasury constant maturity yields from the Federal Reserve H.15 release (read from FRED), 1 month to 30 years | Par yields with semi-annual coupons, bootstrapped |
| ECB | Spot rates on AAA-rated euro area government bonds, 3 months to 30 years | Zero rates, converted to annual compounding |
| Manual | Quotes typed into the table or loaded from a CSV or Excel file | As labelled in each row |

The ECB estimates its spot rates with the Svensson model and publishes them with continuous compounding. A continuous rate $r$ becomes the annually compounded zero rate

$$
z = e^{r} - 1
$$

## Yield and spread measures

**Yield to maturity.** The single flat yield that discounts the bond's cash flows to its dirty price. Solved by bisection.

**Current yield.** The annual coupon divided by the clean price.

**Spread over curve.** The constant $s$ added to every zero rate, or to the flat yield. Given a market price, the engine solves for the spread that reprices the bond. On the zero curve it is the Z-spread of a plain bond and the option-adjusted spread of a callable or putable bond. For a floater it plays the role of the discount margin.

**Yield to call and yield to worst.** For a callable bond, the yield to call assumes redemption at the call price on the first coupon date on or after the first call date. The yield to worst is the lowest of the yield to maturity and the yield to every call date. Put dates are not considered.

## Bond types

### Fixed coupon

Each period pays $c \times F / m$ and the face value $F$ is repaid at maturity.

### Zero coupon

A single payment of the face value at maturity. The coupon frequency still sets the compounding of its yield.

### Perpetual

Coupons are paid forever and principal is never repaid. On a coupon date, with a flat yield compounded at the coupon frequency, the value reduces to

$$
P = \frac{c \times F}{y}
$$

With annual compounding and $m$ coupons per year it is $(c F / m) / ((1 + y)^{1/m} - 1)$.

The engine prices every perpetual the same way, on a flat yield or on a curve. It lists the coupons up to 60 years after the next coupon date and adds a terminal value at that horizon for all later coupons. The terminal value is one coupon divided by the forward rate, including the spread, for the coupon period that follows the horizon. This is exact when the zero rate is flat beyond the horizon. The engine holds the zero rate flat after the last curve node, so it is exact for any curve that ends before the horizon.

### Floating rate

The coupon resets each period to a reference rate plus a quoted margin $QM$. The next coupon is already known from the last reset. Later coupons are projected from the forward rates of the curve, without the spread:

$$
\text{coupon}_i = \left(f_i + QM\right) \frac{F}{m}, \qquad f_i = \frac{DF(t_{i-1}) / DF(t_i) - 1}{t_i - t_{i-1}}
$$

Cash flows are discounted at the curve plus the spread. On a reset date the floater is worth par in two cases, provided the reference rate entered equals the curve's rate for the first period. The first is when the quoted margin and the spread are both zero. The second is when the discount curve is a flat yield compounded at the coupon frequency and the spread equals the quoted margin.

On the bootstrapped curve the spread is added to an annually compounded zero rate, while the quoted margin is a simple rate per coupon period. For a semi-annual floater, equal values then give a price slightly above par: about 100.12 for a 5-year floater with both at 120 basis points and rates near 4%. The spread plays the role of a discount margin, but it is not the figure the market quotes under that name.

Because the coupons move with rates, the duration of a floater priced near par is close to the time until the next reset. A floater priced well away from par has a longer or shorter duration, and it can be negative.

### Step-up coupon

A fixed coupon bond whose coupon rate changes on scheduled dates. Each step applies to coupon periods that start on or after the step date.

### Amortising

Principal is repaid over the life of the bond, so interest is charged on a falling balance.

*Equal principal* repays the same amount each period. *Level payment* keeps interest plus principal constant, as in a mortgage. With balance $B$, periodic rate $r = c / m$ and $n$ periods left:

$$
\text{payment} = B \times \frac{r}{1 - (1 + r)^{-n}}
$$

The **weighted average life** is the average time until each unit of principal is repaid:

$$
WAL = \frac{\sum t_i \times \text{principal}_i}{\sum \text{principal}_i}
$$

The face value entered is treated as the balance outstanding at settlement.

### Callable and putable

A callable bond lets the issuer redeem early at the call price. The issuer does so when rates have fallen, which caps the price the investor can receive. A putable bond lets the investor sell back at the put price, which sets a floor.

Whether the option is used depends on future interest rates, so these bonds are valued on a binomial tree of the short rate using the Ho-Lee model (Ho and Lee, 1986).

**Building the tree.** The tree has one time step per coupon period. Step $i$ runs from $t_i$ to $t_{i+1}$ and has length $\Delta t_i = t_{i+1} - t_i$, with $t_0 = 0$ at settlement. Every step is one coupon period long, except that the first is shorter when settlement falls inside a period. From every node the rate moves up or down with equal probability. Step 0 has a single node. For $i \geq 1$, node $j$ at step $i$ holds the continuously compounded rate for that step

$$
r_{i,j} = r_{i,0} + j \times 2 \sigma \sqrt{t_i / i}
$$

where $\sigma$ is the annual volatility of the short rate. $t_i / i$ is the average length of the steps before $t_i$, so the standard deviation of the rate at $t_i$ is $\sigma \sqrt{t_i}$.

**Calibration.** The lowest rate of each step, $r_{i,0}$, is chosen so that the tree gives exactly the same discount factors as the discount curve. This uses state prices, as in the forward induction of Jamshidian (1991): $Q_{i,j}$ is the value today of 1 paid only if the tree reaches node $j$ at step $i$. The discount factor for the end of step $i$ must satisfy

$$
DF(t_{i+1}) = \sum_{j} Q_{i,j} e^{-r_{i,j} \Delta t_i}
$$

which gives $r_{i,0}$ directly, with no trial and error. The curve used is the zero curve plus the spread, so the tree discounts at the curve plus the bond's spread.

**Rolling back.** Starting from maturity, the value at each node is the average of the two nodes that follow it plus the cash flow paid then, discounted over one step:

$$
V_{i,j} = \left[\tfrac{1}{2}\left(V_{i+1,j} + V_{i+1,j+1}\right) + CF_{i+1}\right] e^{-r_{i,j} \Delta t_i}
$$

On every coupon date from the first call date onward the value is capped at the call price. From the first put date onward it is floored at the put price. The cap and the floor apply to the value after that date's coupon has been paid. The value at the first node is the dirty price.

**Embedded option value.** The price with options minus the price of the same bond without them. It is zero or negative for a call, which belongs to the issuer, and zero or positive for a put, which belongs to the investor. With no options the tree returns exactly the discounted cash flow price.

## Risk measures

**Effective duration** approximates the percentage price change for a 1% parallel move in rates. The engine moves the whole curve up and down by $\Delta = 10$ basis points and reprices:

$$
D = \frac{P_{-} - P_{+}}{2 P_0 \Delta}
$$

$P_0$ is the dirty price, and $P_{-}$ and $P_{+}$ are the prices after the curve moves down and up.

For a fixed coupon bond on a flat yield this approximates the textbook modified duration. The 10 basis point shift leaves a small error that grows with maturity: about 0.0001 for the 8-year bond tested and 0.0007 for a 30-year bond. Repricing is used because it also works for floaters and for bonds with options, whose cash flows change when rates move.

**Convexity** measures the curvature of the price-yield relationship. It is the second derivative of price with respect to rates, divided by price:

$$
C = \frac{P_{-} + P_{+} - 2 P_0}{P_0 \Delta^2}
$$

Together they approximate the price change for a rate move $\Delta y$:

$$
\frac{\Delta P}{P} \approx -D \Delta y + \tfrac{1}{2} C \Delta y^2
$$

A callable bond shows low or negative convexity when rates fall, because its price cannot rise far above the call price. On the tree this figure is rough. With one step per coupon period and a 10 basis point shift it can change sign from one yield level to the next, so read it as an indication only.

**DV01** is the change in the dirty price per 100 of face for a one basis point move: $D \times P_0 \times 0.0001$.

**Macaulay duration** is the present-value-weighted average time of the cash flows:

$$
D_{Mac} = \frac{\sum t_i \times PV_i}{\sum PV_i}
$$

It is reported for fixed coupon, zero coupon, step-up and amortising bonds. On a flat yield it is the textbook Macaulay duration, and modified duration equals $D_{Mac} / (1 + y/k)$. On a zero curve each cash flow is weighted at its own zero rate, which is the Fisher-Weil duration. It differs from the Macaulay duration computed from the bond's yield.

**Rate scenarios.** The Rate scenarios tab reprices the bond after parallel shifts of the curve from -300 to +300 basis points, with the spread held constant.

## Assumptions and limitations

- Coupon periods are regular. There is no issue date, so odd first or last coupons are not modelled.
- Dates are not adjusted for weekends or holidays, and there is no ex-dividend period.
- Every coupon is the annual rate divided by the frequency, in every day count convention.
- In the final coupon period the engine compounds the yield. Excel and the US Treasury market use simple interest there, so prices can differ by up to a few cents per 100 and yields by a few basis points.
- 30/360 is the US rule without its end-of-February adjustment. After a coupon paid on the last day of February, the engine counts one or two more accrued days than Excel.
- Under 30/360, ACT/360 and ACT/365 the days counted can reach the fixed period length a day or two before a coupon date. On those days the clean price is off by a cent or two per 100, and under ACT/360 the accrued interest can slightly exceed the coupon.
- The curve is taken to start on the bond's settlement date, whatever the date of the quotes.
- Treasury yields of 1 and 3 months are treated as par bonds with one semi-annual coupon left, not as simple-interest bill yields. At yields near 4% the zero rates at those two points come out about 4 to 7 basis points lower.
- Default risk enters only through the spread. There is no recovery or default probability model.
- The spread is added to annually compounded zero rates. For a floater it is close to the market's discount margin but not equal to it.
- A floater uses one curve to project its coupons and to discount them. Its reference rate has the same tenor as its coupon period, with no fixing lag, caps or floors.
- Calls and puts can be exercised only on coupon dates, at a single price, with no notice period.
- The Ho-Lee model has constant volatility and no mean reversion, and it allows rates to become negative.
- The tree has one step per coupon period, which is coarse, most of all for annual coupons. Convexity read from the tree is unstable.
- The zero curve is interpolated linearly. It has a kink at each node, and the instantaneous forward rate jumps there.
- A perpetual needs a positive rate at its 60-year horizon.
- The yield and spread solvers search fixed ranges and return the limit when the answer lies outside: -50% to 500% for the yield, and -500 to 5,000 basis points for the spread.

## Validation

The automated tests compare the engine with values calculated by Microsoft Excel and with identities that must hold. Each Excel row is one bond, except the price row, which uses two. The agreement holds while more than one coupon remains. It does not hold in the final coupon period, for 30/360 accrual after a coupon paid on the last day of February, or in the last day or two of a coupon period under the fixed-length conventions.

| Check | Excel function | Result |
|---|---|---|
| Clean price in all four day count conventions | `PRICE` | Equal to 10 decimal places |
| Zero coupon price | `PRICE` | Equal to 10 decimal places |
| Accrued interest | `ACCRINT` | Equal to 10 decimal places |
| Yield from price | `YIELD` | Equal to 10 decimal places |
| Macaulay duration | `DURATION` | Equal to 10 decimal places |
| Macaulay duration divided by (1 + y/k) | `MDURATION` | Equal to 10 decimal places |
| Effective duration | `MDURATION` | Within 0.0001 for the 8-year bond tested. The engine reprices rather than differentiates, and the gap grows with maturity |

Identities tested: the bootstrapped curve reprices every par instrument at 100, a perpetual on a flat yield is worth coupon over yield, a floater is worth par on a flat yield when its margins match and on a curve when both margins are zero, a level payment bond pays the same amount every period, the tree with no options equals the discounted cash flow price, and the solved spread recovers the spread used to price.

## References

- Fabozzi, F. J. *Bond Markets, Analysis, and Strategies*. Pearson.
- Tuckman, B. and Serrat, A. *Fixed Income Securities: Tools for Today's Markets*. Wiley.
- Hull, J. C. *Options, Futures, and Other Derivatives*. Pearson.
- Ho, T. S. Y. and Lee, S.-B. (1986). Term Structure Movements and Pricing Interest Rate Contingent Claims. *Journal of Finance*, 41(5), 1011-1029.
- Jamshidian, F. (1991). Forward Induction and Construction of Yield Curve Diffusion Models. *Journal of Fixed Income*, 1(1), 62-74.
- Microsoft. PRICE, YIELD, ACCRINT, DURATION and MDURATION functions. support.microsoft.com.
- Board of Governors of the Federal Reserve System. Selected Interest Rates (H.15). federalreserve.gov/releases/h15.
- European Central Bank. Euro area yield curves: technical notes. ecb.europa.eu.
