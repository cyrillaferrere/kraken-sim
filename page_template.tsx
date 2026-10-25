import { Page, Section, Text, Grid, Metrics, LineChart, Table, Pie, Rows, Callout, NumberedList, Segmented, useState } from "grok/canvas";

const D: any = __DATA__;

const usd = (v: number) => v == null ? "n.d." : v.toLocaleString("fr-FR", { maximumFractionDigits: 2, minimumFractionDigits: 2 }) + " $";
const pct = (v: number) => v == null ? "n.d." : (v >= 0 ? "+" : "−") + Math.abs(v).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " %";
const sgu = (v: number) => v == null ? "n.d." : (v >= 0 ? "+" : "−") + usd(Math.abs(v));
const tone = (v: number) => (v > 0 ? "success" : v < 0 ? "danger" : undefined) as any;
const n = (v: number) => Number(v >= 100 ? v.toFixed(2) : v.toPrecision(6)).toLocaleString("fr-FR", { maximumFractionDigits: 8 });
const REG: any = { on: "haussier (achats autorisés)", neutral: "neutre (pas de nouvel achat)", off: "baissier (sortie)" };

export default function App() {
  const [ab, setAb] = useState<string>("val");
  const K = D.core, T = D.total, snap = D.snapshot || {};
  const curve: any[] = D.curve;
  const lab = (arr: any[], i: number) => (i === 0 || i === arr.length - 1 || i % Math.max(1, Math.floor(arr.length / 5)) === 0 ? arr[i].t : "");
  const all = curve.flatMap((p: any) => [p.sim, p.btc, p.core ?? p.sim]);
  const lo = Math.min(...all), hi = Math.max(...all), pad = Math.max((hi - lo) * 0.1, D.C0 * 0.01);
  const rs = D.btc_regime_state || (D.btc_regime ? "on" : "off");
  return (
    <Page title="Kraken Sim : trading fictif" width="wide"
      summary={`Simulation papier V1.1 sur les prix publics Kraken : un seul portefeuille de ${usd(D.C0)} géré par la stratégie de tendance, démarré avec un socle de départ BTC/ETH/XRP de ${usd(K.C0)} que la stratégie peut alléger ou vendre selon ses règles. Aucun ordre réel. Au ${D.as_of} (heure de Paris), ${D.n_cycles} cycle(s), démarrage ${D.start_paris}.`}>
      {D.killed ? <Callout tone="danger" lead="Coupe-circuit déclenché">Le drawdown du portefeuille total a atteint 30 % ; toutes les positions (socle de départ compris) ont été liquidées.</Callout> : null}
      <Section heading="Portefeuille vs socle de départ conservé">
        <Table columns={["Référence", "Capital initial", "Valeur", "P&L", "P&L %"]} emphasis={2}
          rows={[["Portefeuille V1.1 (unique)", usd(T.C0), usd(T.equity), { text: sgu(T.pnl), tone: tone(T.pnl) }, { text: pct(T.pnl_pct), tone: tone(T.pnl_pct) }],
            ["Socle de départ conservé sans toucher + liquidités", usd(D.C0), usd(K.bench), { text: sgu(K.bench - D.C0), tone: tone(K.bench - D.C0) }, { text: pct(K.bench_pct), tone: tone(K.bench_pct) }]]} />
        <Text>{`Écart vs socle conservé : ${sgu(K.vs_bench)}. Liquidités ${usd(D.cash)}, exposition ${D.exposure_pct.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %.`}</Text>
      </Section>
      <Section heading="Performance">
        <Grid columns={4}>
          <Metrics metrics={[{ value: usd(T.equity), label: "Valeur totale" }, { value: pct(D.net_return_pct), label: "Rendement total", tone: tone(D.net_return_pct) }]} />
          <Metrics metrics={[{ value: pct(D.vs_btc_pct), label: "vs BTC conservé", detail: "BTC conservé " + pct(D.btc_return_pct), tone: tone(D.vs_btc_pct) }]} />
          <Metrics metrics={[{ value: "−" + D.max_dd_pct.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " %", label: "Drawdown max (total)" }, { value: "−" + D.cur_dd_pct.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " %", label: "Drawdown actuel" }]} />
          <Metrics metrics={[{ value: usd(D.fees), label: "Frais payés", detail: D.n_trades + " transaction(s)" }]} />
        </Grid>
      </Section>
      <Section heading="Évolution" caption="USD, heure de Paris ; BTC conservé = tout le C0 en BTC au départ">
        <LineChart points={curve.map((p: any, i: number) => ({ label: lab(curve, i), value: p.sim }))} floor={lo - pad} ceiling={hi + pad} labels={["Total"]}
          lines={[{ label: "BTC conservé", values: curve.map((p: any) => p.btc) }, { label: "Socle conservé", values: curve.map((p: any) => p.core ?? p.sim) }]}
          secondary={{ label: "C0 total", values: curve.map(() => D.C0) }}
          format={(v: number) => Math.round(v).toLocaleString("fr-FR") + " $"} />
      </Section>
      <Grid columns={2}>
        <Section heading="Répartition">
          <Pie parts={D.allocation.map((a: any) => ({ label: a.label, value: a.value, display: usd(a.value) }))} />
        </Section>
        <Section heading="Socle de départ" caption={"Achat initial du " + (K.start || "n.d.") + " ; vendable par la stratégie"}>
          <Table columns={["Actif", "Qté initiale", "Prix achat", "Frais", "Encore détenu", "Valeur si conservé"]}
            rows={K.positions.map((p: any) => [p.asset, n(p.qty), usd(p.buy_price), usd(p.fee), Math.round(p.held_pct) + " %", usd(p.value)])} />
        </Section>
      </Grid>
      <Section heading="Positions">
        {D.positions.length ? (
          <Table columns={["Actif", "Origine", "Qté", "Prix moyen", "Prix", "Valeur", "P&L", "Stop"]}
            rows={D.positions.map((p: any) => [p.asset, p.origin ? "achat initial" : "stratégie", n(p.qty), usd(p.avg), usd(p.price), usd(p.value), { text: pct(p.pnl_pct), tone: tone(p.pnl_pct) }, p.stop ? usd(p.stop) : "n.d."])} />
        ) : <Text>{`Portefeuille entièrement en liquidités (${usd(D.cash)}) : régime BTC ${REG[rs] || "n.d."}${D.pending.length ? ", " + D.pending.length + " ordre(s) post-only en attente" : ""}.`}</Text>}
      </Section>
      <Section heading="Régime BTC du jour" caption="Figé à la décision journalière">
        <Rows rows={[{ title: "Régime : " + (REG[snap.state] || "n.d."), detail: snap.band ? `Clôture ${usd(snap.btc_close)} vs bande EMA50 ± 0,15×ATR14 [${usd(snap.band[0])} ; ${usd(snap.band[1])}], bougie du ${snap.candle}` : "" },
          { title: "Univers du jour", detail: (snap.universe || D.universe || []).join(", ").replace(/XBT/g, "BTC") },
          { title: "Frais (palier simulé 30 j)", detail: D.fees_tier.maker != null ? `maker ${(D.fees_tier.maker * 100).toLocaleString("fr-FR")} % · taker ${(D.fees_tier.taker * 100).toLocaleString("fr-FR")} % · volume 30 j ${usd(D.fees_tier.vol30)}` : "n.d." }]} />
      </Section>
      {D.indicators.length ? <Section heading="Indicateurs par crypto" caption={"Source : " + D.indicators_src}>
        <Table columns={["Crypto", "Clôture/EMA50", "RSI 14", "ADX", "Vol. 7j/30j", "Momentum", "Score"]}
          rows={D.indicators.map((r: any) => [r.asset, { text: pct(r.ema_pct), tone: r.trend ? "success" : "danger" }, r.rsi == null ? "n.d." : r.rsi.toFixed(1), r.adx == null ? "n.d." : r.adx.toFixed(0), r.vol_ratio == null ? "n.d." : "×" + r.vol_ratio.toFixed(2), pct((r.mom || 0) * 100), { text: r.score + "/5", tone: r.score >= 4 && r.trend ? "success" : undefined }])} />
      </Section> : null}
      <Section heading="Journal des ordres" caption="Heure de Paris">
        <Rows rows={D.journal.map((j: string) => ({ title: j }))} />
      </Section>
      <Section heading="Décisions du dernier cycle">
        <Rows rows={(D.decision_cycles[0] ? D.decision_cycles[0].items : []).filter((d: any) => d.action !== "signal").map((d: any) => ({ lead: d.asset, title: d.action, detail: d.reason }))} />
      </Section>
      {D.ablation ? <Section heading="Ablation V1.04 → V1.1" caption={`Backtest journalier · OPT ${D.ablation.periods.opt} · VAL ${D.ablation.periods.val} · biais du survivant, résultats indicatifs`}>
        <Segmented options={[{ value: "val", label: "Validation" }, { value: "opt", label: "Optimisation" }]} value={ab} onChange={(v: string) => setAb(v)} />
        <Table columns={["Étape", "Rendement", "Drawdown", "A/R par mois", "Profit factor"]}
          rows={D.ablation.steps.map((s: any) => [s.name, { text: pct(s[ab].ret * 100), tone: tone(s[ab].ret) }, "−" + (s[ab].mdd * 100).toFixed(1) + " %", s[ab].rt_month == null ? "n.d." : s[ab].rt_month.toFixed(1), s[ab].pf == null ? "n.d." : s[ab].pf.toFixed(2)])} />
      </Section> : null}
      <Section heading="Règles V1.1">
        <NumberedList items={[
          `Socle de départ : 500 $ BTC, 300 $ ETH, 200 $ XRP achetés le 25/10 à 11h33 (limite maker). Ce sont des positions normales : stop suiveur, sortie risk-off, sortie de tendance et rotation s'appliquent ; sortie de tendance et rotation seulement après 48 h de détention depuis l'achat initial (27/10 11h33).`,
          `Un seul portefeuille de ${usd(D.C0)} : 3 positions max à 33 % du total ; une position < ½ cible (taille socle) n'occupe pas d'emplacement et peut être renforcée à 33 % en régime haussier si elle passe le filtre d'entrée.`,
          "Décision journalière unique vers 00:10 UTC sur bougies clôturées ; cycles horaires (hh:10 UTC) pour les stops et les ordres en attente ; aucun achat dans les 60 min avant 00:00 UTC.",
          "Régime BTC à hystérésis : EMA50 ± 0,15×ATR14 → haussier / neutre / baissier ; nouveaux achats seulement en régime haussier.",
          "Entrée : tendance obligatoire + au moins 4/5 critères (tendance, MACD, RSI 50–75, ADX > 20, volume 7 j > 30 j), classement par momentum ½·30 j + ½·7 j.",
          "Conservation tant que rang ≤ 4, détention min. 48 h, challenger +10 % ; stop suiveur 3×ATR (taker), coupe-circuit à −30 % du C0 total.",
          "Ordres post-only (maker) remplis seulement si des transactions publiques croisent la limite ; frais du palier Kraken sur le volume simulé 30 j.",
        ]} />
        <Text>{`C0 total ${usd(D.C0)} (valeur de repli du portefeuille Kraken de Cyril au 24/10/2026). Le tableau de bord HTML en direct est dans dashboard.html.`}</Text>
      </Section>
    </Page>
  );
}
