
import io
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

def luo_pdf(kuvapolku, arvot_lista):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    flowables = []

    flowables.append(Paragraph("Lämmitysjärjestelmän vertailu – Lähtötiedot ja kuvaaja", styles["Title"]))
    flowables.append(Spacer(1, 0.5 * cm))

    flowables.append(Paragraph("Lähtötiedot:", styles["Heading2"]))
    taulukko = Table(arvot_lista, hAlign="LEFT", colWidths=[9*cm, 5*cm])
    flowables.append(taulukko)
    flowables.append(Spacer(1, 1 * cm))

    flowables.append(Paragraph("Kuvaaja:", styles["Heading2"]))
    flowables.append(Image(kuvapolku, width=15*cm, height=8*cm))

    doc.build(flowables)
    buffer.seek(0)
    return buffer

import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# ---------- LASKENTAFUNKTIOT ----------

def laske_kustannukset_50v(investointi, laina_aika, korko, sahkon_hinta, sahkon_kulutus,
                            korjaus_vali, korjaus_hinta, korjaus_laina_aika,
                            sahkon_inflaatio, kuukausikustannus):
    vuodet = 50
    lyhennys = investointi / laina_aika
    jaljella = investointi
    hinta = sahkon_hinta
    kustannukset = []
    korjauslainat = []
    kk_kulu_v = kuukausikustannus * 12

    for v in range(1, vuodet + 1):
        lyh = lyhennys if v <= laina_aika else 0
        korko_inv = jaljella * (korko / 100) if v <= laina_aika else 0
        if v <= laina_aika:
            jaljella -= lyh

        sahko = hinta * sahkon_kulutus

        if v > 1 and (v - 1) % korjaus_vali == 0:
            korjauslainat.append({
                "jaljella": korjaus_hinta,
                "lyh": korjaus_hinta / korjaus_laina_aika,
                "vuosia": korjaus_laina_aika
            })

        korjaus_lyh = korjaus_korot = 0
        for l in korjauslainat:
            if l["vuosia"] > 0:
                korko_l = l["jaljella"] * (korko / 100)
                korjaus_korot += korko_l
                korjaus_lyh += l["lyh"]
                l["jaljella"] -= l["lyh"]
                l["vuosia"] -= 1
        korjauslainat = [l for l in korjauslainat if l["vuosia"] > 0]

        vuosi_kust = lyh + korko_inv + sahko + korjaus_lyh + korjaus_korot + kk_kulu_v
        kustannukset.append(vuosi_kust)
        hinta *= (1 + sahkon_inflaatio / 100)

    return kustannukset

def laske_kaukolampo_kustannukset(kulutus_mwh, hinta_per_mwh, inflaatio):
    tulos = []
    hinta = hinta_per_mwh
    for _ in range(50):
        tulos.append(kulutus_mwh * hinta)
        hinta *= (1 + inflaatio / 100)
    return tulos

def takaisinmaksuaika(investointi, kaukolampo, maalampo):
    erotus = np.array(kaukolampo) - np.array(maalampo)
    kumulatiivinen = np.cumsum(erotus)
    for vuosi, kertynyt in enumerate(kumulatiivinen, 1):
        if kertynyt >= investointi:
            return vuosi
    return None

# ---------- KÄYTTÖLIITTYMÄ ----------

st.set_page_config(page_title="Lämmitysvertailu – Kulutus", layout="wide")
st.title("Maalämpö vs Kaukolämpö – Kolme eri kulutusvaihtoehtoa")

with st.sidebar:
    st.header("Kulutusvaihtoehdot (MWh/v)")
    kulutus_a = st.number_input("Kulutus A", min_value=0.0, value=700.0, step=50.0)
    kulutus_b = st.number_input("Kulutus B", min_value=0.0, value=850.0, step=50.0)
    kulutus_c = st.number_input("Kulutus C", min_value=0.0, value=1000.0, step=100.0)

    st.header("Maalämpö")
    scop = st.number_input("SCOP (tehokkuus)", min_value=1.0, value=3.5, step=0.1)
    sahkon_hinta = st.number_input("Sähkön hinta (€/kWh)", min_value=0.0, value=0.12, step=0.01)
    sahkon_inflaatio = st.number_input("Sähkön hinnan nousu (%/v)", min_value=0.0, value=2.0, step=0.1)
    investointi = st.number_input("Investointi (€)", min_value=0.0, value=650000.0, step=10000.0)
    laina_aika = st.slider("Laina-aika (v)", 5, 40, 20)
    korko = st.number_input("Korko (%/v)", min_value=0.0, value=3.0, step=0.1)
    korjaus_vali = st.slider("Korjausväli (v)", 5, 30, 15)
    korjaus_hinta = st.number_input("Korjauksen hinta (€)", min_value=0.0, value=20000.0, step=5000.0)
    korjaus_laina_aika = st.slider("Korjauslaina (v)", 1, 30, 10)
    kk_kulu = st.number_input("Kuukausikustannus (€)", min_value=0.0, value=100.0, step=10.0)

    st.header("Kaukolämpö")
    kl_hinta = st.number_input("Hinta (€/MWh)", min_value=0.0, value=100.0, step=10.0)
    kl_inflaatio = st.number_input("Hinnan nousu (%/v)", min_value=0.0, value=2.0, step=0.1)

    st.header("Maksuperuste")
    neliot = st.number_input("Maksavat neliöt (m²)", min_value=1.0, value=1000.0, step=100.0)

# Laskelmat
vuodet = list(range(1, 51))
kulutukset = [kulutus_a, kulutus_b, kulutus_c]
ml_kustannukset = []
kl_kustannukset = []

for kulutus in kulutukset:
    kl = laske_kaukolampo_kustannukset(kulutus, kl_hinta, kl_inflaatio)
    kl_kustannukset.append(kl)

    kwh = (kulutus * 1000) / scop
    ml = laske_kustannukset_50v(investointi, laina_aika, korko, sahkon_hinta, kwh,
                                 korjaus_vali, korjaus_hinta, korjaus_laina_aika,
                                 sahkon_inflaatio, kk_kulu)
    ml_kustannukset.append(ml)

# Kaavio
fig, ax = plt.subplots()
for i, nimi in enumerate(["A", "B", "C"]):
    ax.plot(vuodet, kl_kustannukset[i], "--", label=f"Kaukolämpö {nimi}")
    ax.plot(vuodet, ml_kustannukset[i], label=f"Maalämpö {nimi}")
ax.set_title("Lämmityskustannukset 50 vuoden aikana")
ax.set_xlabel("Vuosi")
ax.set_ylabel("Kustannus (€)")
ax.legend()
ax.grid(True)
st.pyplot(fig, use_container_width=True)


# Vastiketaulukko (€/m²/kk 5 v välein)
st.markdown("### Rahoitus- ja lämmitysvastikkeet (€/m²/kk, 5 v välein)")

def erittely_listat(investointi, laina_aika, korko, sahkon_hinta, sahkon_kulutus, inflaatio,
                    korjaus_vali, korjaus_hinta, korjaus_laina_aika, kuukausikustannus):
    rahoitus, lampo = [], []
    jaljella = investointi
    lyhennys = investointi / laina_aika
    h = sahkon_hinta
    korjauslainat = []
    kk_v = kuukausikustannus * 12

    for v in range(1, 51):
        if v <= laina_aika:
            korko_v = jaljella * (korko / 100)
            rah = lyhennys + korko_v
            jaljella -= lyhennys
        else:
            rah = 0

        if v > 1 and (v - 1) % korjaus_vali == 0:
            korjauslainat.append({
                "jaljella": korjaus_hinta,
                "lyh": korjaus_hinta / korjaus_laina_aika,
                "vuosia": korjaus_laina_aika
            })

        korjaus_lyh = korjaus_korot = 0
        for l in korjauslainat:
            if l["vuosia"] > 0:
                korko_l = l["jaljella"] * (korko / 100)
                korjaus_korot += korko_l
                korjaus_lyh += l["lyh"]
                l["jaljella"] -= l["lyh"]
                l["vuosia"] -= 1
        korjauslainat = [l for l in korjauslainat if l["vuosia"] > 0]

        elec = h * sahkon_kulutus
        lampo.append(elec + korjaus_lyh + korjaus_korot + kk_v)
        rahoitus.append(rah)
        h *= (1 + inflaatio / 100)

    return rahoitus, lampo

taulukko_vuodet = list(range(5, 51, 5))
taulukko_data = []

for i, kulutus in enumerate(kulutukset):
    sahkon_kulutus = (kulutus * 1000) / scop
    rahoitus, lampo = erittely_listat(investointi, laina_aika, korko, sahkon_hinta, sahkon_kulutus,
                                      sahkon_inflaatio, korjaus_vali, korjaus_hinta, korjaus_laina_aika, kk_kulu)
    for y in taulukko_vuodet:
        if i == 0:
            taulukko_data.append({"Vuosi": y})
        taulukko_data[y//5 - 1][f"Rahoitus {chr(65+i)}"] = rahoitus[y-1]/neliot/12
        taulukko_data[y//5 - 1][f"Lämmitys {chr(65+i)}"] = lampo[y-1]/neliot/12
        taulukko_data[y//5 - 1][f"Kaukolämpö {chr(65+i)}"] = kl_kustannukset[i][y-1]/neliot/12

df = pd.DataFrame(taulukko_data).set_index("Vuosi")
st.dataframe(df.style.format("{:.2f}"), use_container_width=True)

# Takaisinmaksuajat

# Luo PDF-kuvaaja ja kerää lähtötiedot
kuvapolku = "/tmp/kuvaaja_streamlit.png"
fig.savefig(kuvapolku)

arvot_lista = [
    ["Kulutus A (MWh/v)", f"{kulutus_a}"],
    ["Kulutus B (MWh/v)", f"{kulutus_b}"],
    ["Kulutus C (MWh/v)", f"{kulutus_c}"],
    ["SCOP", f"{scop}"],
    ["Sähkön hinta (€/kWh)", f"{sahkon_hinta}"],
    ["Sähkön inflaatio (%/v)", f"{sahkon_inflaatio}"],
    ["Investointi (€)", f"{investointi}"],
    ["Laina-aika (v)", f"{laina_aika}"],
    ["Korko (%/v)", f"{korko}"],
    ["Korjausväli (v)", f"{korjaus_vali}"],
    ["Korjaus (€)", f"{korjaus_hinta}"],
    ["Korjauslaina (v)", f"{korjaus_laina_aika}"],
    ["Kuukausikustannus (€)", f"{kk_kulu}"],
    ["Kaukolämmön hinta (€/MWh)", f"{kl_hinta}"],
    ["Kaukolämmön inflaatio (%/v)", f"{kl_inflaatio}"],
    ["Maksavat neliöt (m²)", f"{neliot}"]
]

pdf_buffer = luo_pdf(kuvapolku, arvot_lista)

# Näytä PDF-latauspainike
st.download_button(
    label="📄 Lataa PDF-raportti",
    data=pdf_buffer,
    file_name="lamporatkaisu_raportti.pdf",
    mime="application/pdf"
)

# Takaisinmaksuajat
st.markdown("### Takaisinmaksuaika")
for i, nimi in enumerate(["A", "B", "C"]):
    vuosi = takaisinmaksuaika(investointi, kl_kustannukset[i], ml_kustannukset[i])
    tulos = f"{vuosi} vuotta" if vuosi else "ei 50 vuodessa"
    st.write(f"**Vaihtoehto {nimi}:** {tulos}")

# Lainaosuus
st.markdown(f"**Lainaosuus investoinnille:** {investointi / neliot:,.0f} €/m²")
