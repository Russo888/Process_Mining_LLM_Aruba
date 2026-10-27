"""Grafici della dashboard con scale, ordinamenti ed etichette espliciti."""
import altair as alt
from graphviz import Digraph
from dashboard_data import PERIODS, transition_summary

METRICS = ["Fitness", "Precision", "F1 Score"]
COLORS = ["#38bdf8", "#fbbf24", "#c4b5fd"]


def metric_comparison_chart(table):
    long = table.reset_index().melt(id_vars="Modello", value_vars=METRICS,
                                  var_name="Metrica", value_name="Valore")
    if len(table) > 3:
        # I nomi delle configurazioni richiedono più spazio dei tre algoritmi iniziali.
        return alt.Chart(long).mark_bar().encode(
            y=alt.Y("Modello:N", title=None, sort=table.index.tolist(), axis=alt.Axis(labelLimit=250)),
            yOffset=alt.YOffset("Metrica:N", sort=METRICS),
            x=alt.X("Valore:Q", title="Punteggio (0–1)", stack=None,
                    scale=alt.Scale(domain=[0, 1], nice=False)),
            color=alt.Color("Metrica:N", sort=METRICS,
                            scale=alt.Scale(domain=METRICS, range=COLORS),
                            legend=alt.Legend(orient="bottom", title=None)),
            tooltip=["Modello:N", "Metrica:N", alt.Tooltip("Valore:Q", format=".4f")],
        ).properties(height=max(320, len(table) * 65))
    return alt.Chart(long).mark_bar().encode(
        x=alt.X("Modello:N", title=None, sort=table.index.tolist(), axis=alt.Axis(labelAngle=0, labelLimit=150)),
        xOffset=alt.XOffset("Metrica:N", sort=METRICS),
        y=alt.Y("Valore:Q", title="Punteggio (0–1)", stack=None,
                scale=alt.Scale(domain=[0, 1], nice=False)),
        color=alt.Color("Metrica:N", sort=METRICS,
                        scale=alt.Scale(domain=METRICS, range=COLORS),
                        legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["Modello:N", "Metrica:N", alt.Tooltip("Valore:Q", format=".4f")],
    ).properties(height=320)


def zone_distribution_chart(table):
    return alt.Chart(table).mark_bar(color="#7dd3fc").encode(
        x=alt.X("Eventi compressi:Q", title="Numero di eventi compressi"),
        y=alt.Y("Zona:N", sort=table.Zona.tolist(), title=None, axis=alt.Axis(labelLimit=170)),
        tooltip=["Zona:N", alt.Tooltip("Eventi compressi:Q", format=",")],
    ).properties(height=340)


def period_distribution_chart(table, normalized=True):
    field = "Eventi per ora" if normalized else "Eventi"
    return alt.Chart(table).mark_bar(color="#7dd3fc").encode(
        x=alt.X("Periodo:N", sort=PERIODS, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f"{field}:Q", title="Eventi compressi / ora di calendario" if normalized else "Eventi compressi totali"),
        tooltip=["Periodo:N", alt.Tooltip("Eventi:Q", format=","),
                 alt.Tooltip("Ore di calendario:Q", format=".2f"),
                 alt.Tooltip("Eventi per ora:Q", format=".2f")],
    ).properties(height=340)


def simplified_dfg(df, max_edges=12):
    flows = transition_summary(df)
    top = flows.head(max_edges)
    graph = Digraph("observed_dfg")
    graph.attr(rankdir="LR", bgcolor="transparent", nodesep="0.35", ranksep="0.5")
    graph.attr("node", shape="box", style="rounded,filled", fillcolor="#e0f2fe",
               color="#0284c7", fontcolor="#0f172a", fontname="Arial", fontsize="16", margin="0.15")
    graph.attr("edge", color="#94a3b8", fontcolor="#e2e8f0", fontname="Arial", fontsize="14")
    zones = sorted(set(top.Da) | set(top.A))
    ids = {zone: f"z{i}" for i, zone in enumerate(zones)}
    for zone in zones:
        graph.node(ids[zone], label=zone.replace("_", "\n"))
    for row in top.itertuples(index=False):
        graph.edge(ids[row.Da], ids[row.A], label=f"{row.Frequenza:,}")
    return graph, len(flows), int(top.Frequenza.sum()), int(flows.Frequenza.sum())
