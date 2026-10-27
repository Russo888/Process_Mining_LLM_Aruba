"""Statistiche di presentazione calcolate sull'intero event log, senza modificarlo."""
import pandas as pd

CASE = "case:concept:name"
ZONE = "concept:name"
TIME = "time:timestamp"
PERIODS = ["Notte", "Mattina", "Pomeriggio", "Sera"]
BOUNDS = [(0, 6), (6, 12), (12, 19), (19, 24)]


def event_periods(df):
    hour = pd.to_datetime(df[TIME]).dt.hour
    return pd.Series(pd.cut(hour, bins=[-1, 5, 11, 18, 23], labels=PERIODS), index=df.index)


def period_summary(df):
    """Eventi/ore di calendario nella finestra globale; corregge i giorni di bordo.

    Le ore non sono durata di presenza né una misura di uptime dei sensori.
    Non vengono dedotti eventuali buchi interni di acquisizione.
    """
    work = df.assign(Periodo=event_periods(df))
    counts = work.groupby("Periodo", observed=False).agg(
        Eventi=(ZONE, "size"), Casi=(CASE, "nunique")).reindex(PERIODS, fill_value=0)
    exposure = dict.fromkeys(PERIODS, 0.0)
    if not df.empty:
        timestamps = pd.to_datetime(df[TIME])
        first, last = timestamps.min(), timestamps.max()
        for day in pd.date_range(first.normalize(), last.normalize(), freq="D"):
            for name, (start_hour, end_hour) in zip(PERIODS, BOUNDS):
                start = max(first, day + pd.Timedelta(hours=start_hour))
                end = min(last, day + pd.Timedelta(hours=end_hour))
                exposure[name] += max(0, (end - start).total_seconds() / 3600)
    counts["Ore di calendario"] = pd.Series(exposure)
    counts["Eventi per ora"] = counts["Eventi"].div(
        counts["Ore di calendario"].where(counts["Ore di calendario"] > 0))
    return counts.rename_axis("Periodo").reset_index()


def zone_summary(df):
    return df.groupby(ZONE).size().rename("Eventi compressi").reset_index().rename(
        columns={ZONE: "Zona"}).sort_values(["Eventi compressi", "Zona"], ascending=[False, True])


def transition_summary(df):
    """Conta i follows per caso; evita archi artificiali attraverso casi diversi."""
    work = df.sort_values(TIME, kind="stable")[[CASE, ZONE]].copy()
    work["A"] = work.groupby(CASE, sort=False)[ZONE].shift(-1)
    pairs = work.dropna(subset=["A"]).rename(columns={ZONE: "Da"})
    return pairs.groupby(["Da", "A"]).size().rename("Frequenza").reset_index().sort_values(
        ["Frequenza", "Da", "A"], ascending=[False, True, True]).reset_index(drop=True)


def daily_summary(df, max_groups=28):
    """Tutti i giorni, aggregati in intervalli contigui se il log è molto lungo."""
    if df.empty:
        return pd.DataFrame(columns=["Dal", "Al", "Eventi", "Casi"])
    work = df.copy()
    dates = pd.to_datetime(work[TIME]).dt.normalize()
    first, last = dates.min(), dates.max()
    span = (last - first).days + 1
    width = max(1, (span + max_groups - 1) // max_groups)
    work["Dal"] = first + pd.to_timedelta(((dates - first).dt.days // width) * width, unit="D")
    result = work.groupby("Dal").agg(Eventi=(ZONE, "size"), Casi=(CASE, "nunique")).reset_index()
    result["Al"] = result["Dal"].map(lambda d: min(d + pd.Timedelta(days=width-1), last))
    for key in ("Dal", "Al"):
        result[key] = result[key].dt.strftime("%Y-%m-%d")
    return result[["Dal", "Al", "Eventi", "Casi"]]
