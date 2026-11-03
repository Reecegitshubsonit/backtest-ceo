from kalshibot import leaders as L

PAGE = """<html><body><div>Stats as of Nov 2, 2026, 4:00 AM ET</div> Kalshi Some Name somename +$96.6K Tracked Trades 4,221
First Seen Aug 22, 2026 Last Trade Nov 2, 2026 somename is a Kalshi trader with 4,221 trades tracked by RivoMarkets,
2,000 wins and 1,500 losses on settled markets. Win rate 57% Money traded $3.1M Avg entry 34&cent; <b>Avg entry 34¢</b>
Categories Trades Won Profit NFL 1533 60% +$60.5K Parlays 171 10% +$2.0K MMA 1274 55% -$1.4K Side taken Yes 60 % 40 % No
If you had copied somename $100 per bet , last 90 days +$39,462.00 Profit on $117,100.00 staked 500-671 Record 43% win rate
+34% Return Profit over time 1171 settled trades 1.53× Profit factor +9.0 pts Edge vs implied 43% won at 34¢ avg
Longest losing streak 12 Tracked entries, settled markets. Biggest wins 1 Some market $5K on Yes at 30¢ , Oct 1 +$15.4K
Profit by month Aug 2026 +$15.6K Sep 2026 +$23.6K Oct 2026 +$60.3K Nov 2026 -$3.0K Kalshi leaderboards</body></html>"""


def test_parse_trader():
    t = L.parse_trader("somename", PAGE)
    assert t.profit == 96600 and t.tracked == 4221 and t.last_trade == "Nov 2, 2026"
    assert (t.wins, t.losses, t.avg_entry) == (2000, 1500, 0.34)
    assert t.parlay_trades == 171 and t.top_categories[0] == ["NFL", 1533, 60500.0]
    assert t.sim_n == 1171 and t.sim_avg_entry == 0.34 and abs(t.sim_return - 39462 / 117100) < 1e-9
    assert t.sim_profit_factor == 1.53 and t.biggest_win == 15400
    assert t.months["Nov 2026"] == -3000


def test_score_passes_and_charges_costs():
    t = L.score(L.parse_trader("somename", PAGE), L.Rules())
    assert t.reasons == []
    expected = 39462 / 117100 - 0.07 * 0.66 - 0.02 / 0.34
    assert abs(t.net_return - expected) < 1e-9 and t.t_stat > 5


def test_filters():
    mm = PAGE.replace("Kalshi Some", "Market makers buy both sides Kalshi Some")
    assert "market maker" in L.score(L.parse_trader("x", mm), L.Rules()).reasons
    idle = PAGE.replace("Last Trade Nov 2, 2026", "Last Trade Sep 1, 2026")
    assert any(r.startswith("idle") for r in L.score(L.parse_trader("x", idle), L.Rules()).reasons)
    closer = PAGE.replace("won at 34¢ avg", "won at 96¢ avg")
    assert any(r.startswith("avg entry") for r in L.score(L.parse_trader("x", closer), L.Rules()).reasons)
    nosim = PAGE.replace("+$39,462.00 Profit", "Nothing to simulate +$0 Profit")
    assert "no 90d copy sim" in L.score(L.parse_trader("x", nosim), L.Rules()).reasons


def test_leaderboard_names():
    assert L.leaderboard_names('<a href="/trader/kalshi/a.b">x</a><a href="/trader/kalshi/c">') == ["a.b", "c"]
