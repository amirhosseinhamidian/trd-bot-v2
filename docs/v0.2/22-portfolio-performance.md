# TB2-020 — Portfolio performance analytics

Base: `10fc5d7` (TB2-019). Contract: `portfolio-analytics-v1`.

## Read-only API and source of truth

`GET /api/v1/research/portfolios/{portfolio_id}/analytics` reads the complete
persisted portfolio, not a page of positions or events. Missing portfolio: 404.
POST to this analytics path: 405. No migration, external price request, ledger
mutation, execution action or additional order endpoint is introduced.

`as_of` is `portfolio.updated_at`. All durations stop at this timestamp, never
at the current clock. Timeline points preserve event sequence and UTC timestamps;
non-monotonic timestamps fail closed. Equal timestamps retain sequence order.
Charts use step-after observations and share the API points with an expandable
evidence table. No interpolated prices or benchmark are fabricated.
If the parallel portfolio and analytics reads have different snapshot times,
the UI asks for a reload rather than combining different versions.

## Accounting and definitions

| Metric | Definition |
| --- | --- |
| Net PnL | ending equity minus starting cash |
| Accounting reconciliation | closed net PnL + open gross unrealized PnL − open entry fees = net PnL |
| Return | net PnL / starting cash; not annualized |
| Paid fees | all recorded entry and exit fees, including entry fees of open positions |
| Closed-trade win/loss/breakeven | sign of realized PnL after both entry and exit fees |
| Win rate | profitable closed positions / all closed positions, including breakeven |
| Profit factor | sum of positive closed net PnL / absolute sum of negative closed net PnL |
| Expectancy | sum of closed net PnL / closed count, in ledger quote units |
| Average hold | arithmetic mean of closed_at − opened_at, seconds; excludes open positions |
| Observed duration | updated_at − created_at, seconds |
| Drawdown | (running equity high − event equity) / running high, including recorded marks and fees |
| Drawdown duration | last high timestamp to recovery or last stored event; recovery point retains completed duration |
| Current drawdown duration | zero at recovery; otherwise time since last high |
| Open exposure | sum of quantity × last stored price, gross for either long or short |
| Exposure fraction | gross open exposure / positive ending equity; undefined for nonpositive equity |
| Trades by pair | open/closed counts, closed net PnL and all fees, grouped by base/quote/market |
| Exit mix | one count per closed position from exact matching portfolio/position journal evidence |

No future exit fee is assumed for an open position. Marks need not be fresh;
the UI labels them as recorded historical values. Duration has event-time
resolution; no intra-event peak or intraday risk is inferred. Drawdown may
exceed 100% when a simulated short produces negative equity.

Trade metrics with a zero denominator are `null`. Profit-factor status is
`no_closed_trades`, `no_losses`, or `available`; a profitable-only portfolio is
not represented by infinity or zero. Empty portfolios retain a flat creation
point and zero return/drawdown, but no win rate, expectancy or average hold.
Ratios of trade statistics use Decimal, round-half-up to eight decimal places.
Equity, return and drawdown points retain Decimal precision; UI rounds only
for display. This is not a multi-currency conversion system: aggregation uses
the existing ledger's numeric quote units without introducing FX conversion.

Exit evidence is selected by portfolio in the database using the existing
portfolio index. Position snapshots must match exactly. Duplicate evidence is
deduplicated; missing or conflicting reasons become `unknown`. Counts therefore
sum to closed count, including legacy positions without journals.

## Verification added

- Golden fee/open/closed reconciliation: 1000 starting cash, 19.58 closed net,
  −10 gross open PnL, 0.10 open entry fee, ending equity 1009.48 and total fees 0.52.
- Mixed winner/loser/breakeven, no trades, no losses, fee-induced net loss,
  short negative equity, recovered/unrecovered drawdown duration, deterministic
  output, no mutation and scoped/deduplicated exit evidence.
- API serialization, 404/405 and targeted journal repository selection.
- English/Persian UI, undefined metrics, evidence-table/chart parity and
  uncached encoded client requests.

Runtime gates must be executed locally. Static review is not a passing test
claim. Final PostgreSQL/CI acceptance remains TB2-024; Position Detail remains TB2-021.
