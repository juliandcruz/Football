import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

st.set_page_config(
    page_title="ValueBet Football",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container {max-width: 1200px; padding: 1rem .8rem 5rem .8rem;}
h1 {font-size: 1.8rem !important;}
h2 {font-size: 1.35rem !important;}
h3 {font-size: 1.05rem !important;}
[data-testid="stMetricValue"] {font-size: 1.25rem;}
.value-card {
  padding: 14px; border-radius: 16px; border: 1px solid rgba(128,128,128,.25);
  margin-bottom: 10px; background: rgba(128,128,128,.05);
}
.small {font-size:.82rem; opacity:.75;}
.big {font-size:1.25rem; font-weight:700;}
.badge {font-weight:700; padding:3px 8px; border-radius:999px;}
</style>
""", unsafe_allow_html=True)

def load_csv():
    p = Path("data/value_bets.csv")
    if p.exists():
        return pd.read_csv(p)
    return pd.DataFrame()

def demo_data():
    return pd.DataFrame([
        ["Real Madrid","Real Sociedad","Córners Madrid","+5.5",67,1.70,1.49,13.9,"🔥 VALUE ALTO"],
        ["Real Madrid","Real Sociedad","Tarjetas Real Sociedad","+1.5",71,1.60,1.41,13.6,"🔥 VALUE ALTO"],
        ["Real Madrid","Real Sociedad","Mbappé tiros a puerta","+1.5",54,2.10,1.85,13.4,"🔥 VALUE ALTO"],
        ["Real Madrid","Real Sociedad","Madrid goles","+2.5",57,1.90,1.75,8.3,"🔥 VALUE ALTO"],
        ["Real Madrid","Real Sociedad","Portero Madrid paradas","+1.5",39,2.20,2.56,-14.2,"🔴 PASAR"],
    ], columns=["home","away","market","line","probability","odds","fair_odds","ev","rating"])

def main():
    st.title("⚽ ValueBet Football")
    st.caption("Probabilidades + cuotas + EV. Herramienta de investigación, no garantía de beneficio.")

    df = load_csv()
    if df.empty:
        df = demo_data()
        st.info("Modo demostración. Cuando conectes el pipeline de V2/V3, esta tabla se alimentará automáticamente.")

    # Normalización
    for c in ["probability","odds","fair_odds","ev"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "probability" in df and df["probability"].max() <= 1.0:
        df["probability_pct"] = df["probability"] * 100
    else:
        df["probability_pct"] = df["probability"]

    # Header metrics
    good = df[df["ev"] >= 0.03] if "ev" in df else pd.DataFrame()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Oportunidades", len(good))
    c2.metric("Value alto", int((df["ev"] >= 0.08).sum()))
    c3.metric("EV máximo", f"{df['ev'].max():.1f}%")
    c4.metric("Cuota media", f"{df['odds'].mean():.2f}")

    st.divider()

    # Filters
    with st.expander("Filtros", expanded=True):
        a,b,c = st.columns(3)
        min_ev = a.slider("EV mínimo", -20, 30, 3, 1)
        max_odds = b.slider("Cuota máxima", 1.01, 10.0, 5.0, .05)
        only_value = c.checkbox("Solo apuestas con value", True)

    x = df.copy()
    if only_value:
        x = x[x.ev >= min_ev/100]
    x = x[x.odds <= max_odds].sort_values("ev", ascending=False)

    st.subheader("🔥 Mejores oportunidades")

    for _, r in x.head(12).iterrows():
        ev_pct = float(r.ev)*100
        prob = float(r.probability_pct)
        fair = float(r.fair_odds)
        odds = float(r.odds)
        rating = r.rating
        st.markdown(f"""
        <div class="value-card">
          <div class="small">{r.home} — {r.away}</div>
          <div class="big">{r.market} {r.line} &nbsp; {rating}</div>
          <div style="display:flex;gap:22px;flex-wrap:wrap;margin-top:8px">
            <span>Prob. <b>{prob:.1f}%</b></span>
            <span>Cuota <b>{odds:.2f}</b></span>
            <span>Justa <b>{fair:.2f}</b></span>
            <span>EV <b>{ev_pct:+.1f}%</b></span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.subheader("📊 Tabla completa")
    show_cols = [c for c in ["home","away","market","line","probability_pct","odds","fair_odds","ev","rating"] if c in x]
    y=x[show_cols].copy()
    if "probability_pct" in y: y["probability_pct"]=y["probability_pct"].round(1)
    if "ev" in y: y["ev"]=(y["ev"]*100).round(1)
    st.dataframe(y, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("💰 Simulador de stake")
    bank = st.number_input("Bankroll (€)", min_value=10.0, value=500.0, step=50.0)
    frac = st.slider("Kelly fraccionado", 0.05, 0.50, 0.25, 0.05)
    cap = st.slider("Máximo por apuesta (% bankroll)", 0.25, 5.0, 2.0, 0.25)

    if not x.empty:
        s=x.iloc[0]
        p=float(s.probability_pct)/100
        o=float(s.odds)
        b=o-1
        raw=((b*p)-(1-p))/b if b>0 else 0
        stake=max(0,min(raw*frac,cap/100))*bank
        st.success(f"Para la mejor oportunidad: stake orientativo **€{stake:.2f}** ({stake/bank*100:.2f}% del bankroll).")
        st.caption("El stake es una referencia matemática. No implica que la apuesta sea segura.")

    st.divider()
    st.caption("V3 — Mobile-first. Para producción: conectar cuotas en tiempo real, datos de jugadores, autenticación y base de datos.")

if __name__ == "__main__":
    main()
