import streamlit as st
import pandas as pd
from io import BytesIO
import pdfplumber, re, qrcode
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import json, os
from datetime import datetime

st.set_page_config(page_title="NUGENSER • Presupuestos", page_icon="🧱", layout="wide")
# --- Branding NUGENSER ---
NGS_VERDE = "#1e402d"  # verde oscuro Nugenser
NGS_ACCENT = "#27a742" # acento
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap');
html, body, [class*="css"]  { font-family: 'Montserrat', sans-serif; }
h1, h2, h3 { color: #1e402d; }
.stButton>button { background: #1e402d; color: #fff;…
[13:49, 18/10/2025] Julieta Carbonetti: import streamlit as st
import pandas as pd
from io import BytesIO
import pdfplumber, re, qrcode
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import json, os
from datetime import datetime

# ----------------------------
# Config & Branding NUGENSER
# ----------------------------
st.set_page_config(page_title="NUGENSER • Presupuestos", page_icon="🧱", layout="wide")

NGS_VERDE = "#1e402d"   # verde oscuro Nugenser
NGS_ACCENT = "#27a742"  # acento
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }
h1, h2, h3 { color: #1e402d; }
.stButton>button { background: #1e402d; color: #fff; border-radius: 6px; }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Login simple (Julieta / Cacho)
# ----------------------------
def check_login(user, pwd):
    env_pwd = os.environ.get(f"{user.upper()}_PASS")
    demo_pwd = "demo"   # por si no configuran secrets aún
    expected = env_pwd if env_pwd else demo_pwd
    return pwd == expected

if "logged" not in st.session_state:
    st.session_state.logged = False
    st.session_state.user = None

logo_path = "assets/logo.png"
col_logo, col_title = st.columns([1,5])
with col_logo:
    try:
        st.image(logo_path, caption="NUGENSER S.A – ALUMINIO & PVC", use_container_width=True)
    except:
        st.write("NUGENSER")
with col_title:
    st.markdown("<h2 style='margin-bottom:0'>Presupuestos</h2><small>App interna</small>", unsafe_allow_html=True)

if not st.session_state.logged:
    st.divider()
    st.subheader("Ingreso")
    user = st.selectbox("Usuario", ["Julieta","Cacho"])
    pwd = st.text_input("Contraseña", type="password", placeholder="demo")
    if st.button("Entrar"):
        if check_login(user, pwd):
            st.session_state.logged = True
            st.session_state.user = user
            st.success(f"Bienvenida/o, {user} ✔️")
        else:
            st.error("Contraseña incorrecta")
    st.stop()

# ----------------------------
# Datos base & Helpers
# ----------------------------
DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "cliente": {"cliente":"", "obra":"", "arquitecto":"", "contacto":""},
        "params": {"moneda_salida":"USD", "tc":1400.0, "iva":21.0, "margen_global":35.0},
        "items": [],
        "margenes": [
            {"proveedor":"Alcemar", "categoria":"Perfiles/Accesorios", "margen":35.0},
            {"proveedor":"Alcemar", "categoria":"Premarcos", "margen":35.0},
            {"proveedor":"Alcemar", "categoria":"Sobreguías", "margen":35.0},
            {"proveedor":"Casa de los Cristales", "categoria":"Vidrios", "margen":30.0},
            {"proveedor":"Alum-Tec", "categoria":"PVC", "margen":25.0},
            {"proveedor":"—", "categoria":"Mano de obra", "margen":40.0},
            {"proveedor":"—", "categoria":"Colocación", "margen":40.0},
            {"proveedor":"—", "categoria":"Flete/Grúa", "margen":0.0},
        ]
    }

def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def margin_lookup(margenes, proveedor, categoria, fallback):
    for m in margenes:
        if m["proveedor"] == proveedor and m["categoria"] == categoria:
            return float(m.get("margen", fallback))
    return fallback

def calcular(df, params, margenes):
    rows = []
    for _, row in df.iterrows():
        cant = float(row.get("cantidad") or 0)
        pu_prov = float(row.get("precio_proveedor") or 0)
        moneda = row.get("moneda") or "USD"
        iva_incl = (row.get("iva_incl") or "N") == "S"
        proveedor = row.get("proveedor") or ""
        categoria = row.get("categoria") or ""
        margen_linea = row.get("margen_opc")

        margen = float(margen_linea) if (margen_linea not in (None, "")) else margin_lookup(
            margenes, proveedor, categoria, float(params["margen_global"])
        )

        neto_sin_iva = pu_prov / (1 + float(params["iva"]) / 100) if iva_incl else pu_prov
        pu_margen = neto_sin_iva * (1 + margen / 100)
        total_moneda = pu_margen * cant
        tc = float(params["tc"]) if moneda == "USD" else 1.0

        rows.append({
            **row,
            "neto_sin_iva": round(neto_sin_iva, 2),
            "margen_usado_%": round(margen, 2),
            "pu_margen": round(pu_margen, 2),
            "total_moneda": round(total_moneda, 2),
            "tc_usado": tc,
            "total_ars": round(total_moneda * tc, 2),
        })
    return pd.DataFrame(rows)

# ----------------------------
# Importador Alum-Tec (detallado)
# ----------------------------
def _norm(t: str) -> str:
    return re.sub(r"[ \t]+", " ", (t or "").replace("\xa0", " ").upper()).strip()

def parse_alumtec_blocks(file_bytes: bytes):
    """
    Lee PDF Alum-Tec y devuelve (posiciones, totalesUSD)
    posiciones: [{posicion, tipologia, medidas, sistema, vidrio, color, descripcion}]
    totales: {TOTAL_PROYECTO, TOTAL_CON_DTO, IVA_21, TOTAL_FINAL}
    """
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        full = "\n".join([(p.extract_text() or "") for p in pdf.pages])
    txt = _norm(full)

    # Totales (USD)
    money = r"(\d{1,3}(?:[\.,]\d{3})*(?:[\.,]\d{2})?)"
    totales = {}
    for k, pat in {
        "TOTAL_PROYECTO": r"TOTAL\s+PROYECTO[:\s]+USD\s+" + money,
        "DESCUENTO":      r"DESCUENTO\s+(\d{1,2})%\s*[:\s]+USD\s+" + money,
        "TOTAL_CON_DTO":  r"TOTAL\s+CON\s+DTO\.?[:\s]+USD\s+" + money,
        "IVA_21":         r"IVA\s*21%\s*[:\s]+USD\s+" + money,
        "TOTAL_FINAL":    r"TOTAL\s+FINAL[:\s]+USD\s+" + money,
    }.items():
        m = re.search(pat, txt)
        if m:
            val = m.groups()[-1].replace(".", "").replace(",", ".")
            try:
                totales[k] = float(val)
            except:
                pass

    # Cortar en bloques V1..Vn
    lines = [l for l in txt.splitlines() if l.strip()]
    raw_blocks, current = [], []
    for line in lines:
        if re.match(r"^V\d+\b", line.strip()):
            if current:
                raw_blocks.append("\n".join(current))
                current = []
        current.append(line)
    if current:
        raw_blocks.append("\n".join(current))

    # Parsear campos dentro de cada bloque
    parsed = []
    for block in raw_blocks:
        b = _norm(block)
        pos = re.search(r"^(V\d+)\b", b)
        tip = re.search(r"(TIPOLOG[IÍ]A|TIP):\s*([A-Z0-9 \-/]+)", b)
        med = re.search(r"(MEDIDAS|DIMENSIONES|TAMANO|TAMAÑO):\s*([0-9., Xx]+)", b)
        sis = re.search(r"(SISTEMA|SERIE|LINEA|L[IÍ]NEA):\s*([A-Z0-9 \-/]+)", b)
        vid = re.search(r"(VIDRIO|DVH|LAMINADO|TERMOPANEL):\s*([A-Z0-9 +/\.]+)", b)
        col = re.search(r"(COLOR|TERMINACI[ÓO]N):\s*([A-Z0-9 \-/]+)", b)

        parsed.append({
            "posicion":  pos.group(1) if pos else "",
            "tipologia": (tip.group(2).title() if tip else "").strip(),
            "medidas":   (med.group(2).replace("X", "x") if med else "").strip(),
            "sistema":   (sis.group(2).title() if sis else "").strip(),
            "vidrio":    (vid.group(2).upper() if vid else "").strip(),
            "color":     (col.group(2).title() if col else "").strip(),
            "descripcion": b.split("\n", 1)[0].title() if "\n" in b else b.title(),
        })
    return parsed, totales

# ----------------------------
# UI
# ----------------------------
data = load_data()
st.sidebar.write(f"👤 {st.session_state.user}")
page = st.sidebar.radio(
    "Navegación",
    ["Presupuesto", "Config", "Importar Alum-Tec (detallado)", "Exportar PDF"]
)

# --- Presupuesto ---
if page == "Presupuesto":
    st.header("Presupuesto")
    colA,colB,colC,colD = st.columns(4)
    with colA:
        data["cliente"]["cliente"] = st.text_input("Cliente", value=data["cliente"]["cliente"])
        data["cliente"]["obra"] = st.text_input("Obra", value=data["cliente"]["obra"])
    with colB:
        data["cliente"]["arquitecto"] = st.text_input("Arquitecto", value=data["cliente"]["arquitecto"])
        data["cliente"]["contacto"] = st.text_input("Contacto (Tel/WhatsApp)", value=data["cliente"]["contacto"])
    with colC:
        data["params"]["moneda_salida"] = st.selectbox("Moneda de salida", ["USD","ARS"], index=["USD","ARS"].index(data["params"]["moneda_salida"]))
        data["params"]["tc"] = st.number_input("Tipo de cambio (si USD→ARS)", min_value=0.0, value=float(data["params"]["tc"]), step=10.0)
    with colD:
        data["params"]["iva"] = st.number_input("IVA (%)", min_value=0.0, value=float(data["params"]["iva"]), step=1.0)
        data["params"]["margen_global"] = st.number_input("Margen global (%)", min_value=0.0, value=float(data["params"]["margen_global"]), step=1.0)

    st.write("---")
    st.subheader("Ítems del presupuesto (pegá líneas de proveedor)")
    st.caption("Proveedor, Categoría, Descripción, Cantidad, UM, Precio Proveedor, Moneda (USD/ARS), ¿IVA incl.? (S/N), Margen % (opcional)")

    df_items = pd.DataFrame(data["items"] or [], columns=["proveedor","categoria","descripcion","cantidad","um","precio_proveedor","moneda","iva_incl","margen_opc"])
    if df_items.empty:
        df_items = pd.DataFrame(columns=["proveedor","categoria","descripcion","cantidad","um","precio_proveedor","moneda","iva_incl","margen_opc"])

    edited = st.data_editor(df_items, num_rows="dynamic", height=350, use_container_width=True)

    calc = calcular(edited.copy(), data["params"], data["margenes"])
    st.markdown("#### Cálculo")
    st.dataframe(calc, use_container_width=True, height=260)

    subtotal_ars = float(calc["total_ars"].sum()) if not calc.empty else 0.0
    iva_monto = subtotal_ars * (float(data["params"]["iva"])/100)
    total_c_iva = subtotal_ars + iva_monto

    c1,c2,c3 = st.columns(3)
    c1.metric("Subtotal (ARS)", f"$ {subtotal_ars:,.2f}")
    c2.metric("IVA", f"$ {iva_monto:,.2f}")
    c3.metric("Total c/IVA (ARS)", f"$ {total_c_iva:,.2f}")

    if st.button("Guardar cambios"):
        data["items"] = edited.fillna("").to_dict(orient="records")
        save_data(data)
        st.success("Guardado ✔️")

# --- Config ---
elif page == "Config":
    st.header("Configuración")
    st.subheader("Márgenes por proveedor/categoría")
    df_m = pd.DataFrame(data["margenes"] or [], columns=["proveedor","categoria","margen"])
    if df_m.empty:
        df_m = pd.DataFrame(columns=["proveedor","categoria","margen"])
    df_m_edit = st.data_editor(df_m, num_rows="dynamic", height=280, use_container_width=True)

    st.subheader("Parámetros generales")
    col1,col2,col3 = st.columns(3)
    with col1:
        data["params"]["moneda_salida"] = st.selectbox("Moneda de salida", ["USD","ARS"], index=["USD","ARS"].index(data["params"]["moneda_salida"]))
    with col2:
        data["params"]["tc"] = st.number_input("Tipo de cambio", min_value=0.0, value=float(data["params"]["tc"]), step=10.0)
    with col3:
        data["params"]["iva"] = st.number_input("IVA (%)", min_value=0.0, value=float(data["params"]["iva"]), step=1.0)
    data["params"]["margen_global"] = st.number_input("Margen global (%)", min_value=0.0, value=float(data["params"]["margen_global"]), step=1.0)

    if st.button("Guardar configuración"):
        data["margenes"] = df_m_edit.fillna("").to_dict(orient="records")
        save_data(data)
        st.success("Guardado ✔️")

# --- Importar Alum-Tec (detallado) ---
elif page == "Importar Alum-Tec (detallado)":
    st.header("Importar PDF — Alum-Tec (PVC) con detalle V1..Vn")
    pdf = st.file_uploader("Soltá el PDF de Alum-Tec", type=["pdf"])
    colA, colB = st.columns(2)
    with colA:
        marg_lineas = st.number_input(
            "Margen por línea (%)",
            min_value=0.0,
            value=float(data["params"].get("margen_global", 35.0)),
            step=1.0
        )
    with colB:
        tc = st.number_input(
            "Tipo de cambio (USD→ARS)",
            min_value=0.0,
            value=float(data["params"].get("tc", 1400.0)),
            step=10.0
        )

    if pdf is not None and st.button("Procesar PDF"):
        raw = pdf.read()
        posiciones, totales = parse_alumtec_blocks(raw)
        if not posiciones:
            st.warning("No detecté bloques V1..Vn. Pasame ese PDF y lo ajusto.")
        else:
            st.success(f"Detecté {len(posiciones)} posiciones")
            df = pd.DataFrame(posiciones)
            # preparar para empujar a Ítems
            df["proveedor"] = "Alum-Tec"; df["categoria"] = "PVC"
            df["cantidad"] = 1; df["um"] = "u"
            df["precio_proveedor"] = 0.0
            df["moneda"] = "USD"; df["iva_incl"] = "N"
            df["margen_opc"] = marg_lineas

            st.caption("Revisá/ajustá antes de importar ↓")
            edited = st.data_editor(df, num_rows="fixed", use_container_width=True, height=440)

            if st.button("Agregar a Ítems"):
                base = pd.DataFrame(
                    data["items"] or [],
                    columns=[
                        "proveedor","categoria","descripcion","cantidad","um",
                        "precio_proveedor","moneda","iva_incl","margen_opc"
                    ]
                )
                rows = []
                for _, r in edited.iterrows():
                    desc = f"{r.get('posicion','')} • {r.get('tipologia','')} • {r.get('sistema','')} • {r.get('medidas','')} • {r.get('vidrio','')} • {r.get('color','')}"
                    rows.append({
                        "proveedor": r.get("proveedor","Alum-Tec"),
                        "categoria": r.get("categoria","PVC"),
                        "descripcion": desc.strip(" •"),
                        "cantidad": int(r.get("cantidad") or 1),
                        "um": r.get("um") or "u",
                        "precio_proveedor": float(r.get("precio_proveedor") or 0.0),
                        "moneda": r.get("moneda") or "USD",
                        "iva_incl": r.get("iva_incl") or "N",
                        "margen_opc": float(r.get("margen_opc") or marg_lineas),
                    })
                merged = pd.concat([base, pd.DataFrame(rows)], ignore_index=True)
                data["items"] = merged.fillna("").to_dict(orient="records")
                save_data(data)
                st.success("Se importaron las aberturas a Ítems ✔️")

        if totales:
            st.markdown("### Totales detectados (USD)")
            st.json(totales)

# --- Exportar PDF ---
else:
    st.header("Exportar PDF")
    st.caption("Genera un PDF con carátula, totales e información técnica IRAM 12565/12595.")
    c = data["cliente"]; p = data["params"]
    df_items = pd.DataFrame(data["items"] or [], columns=["proveedor","categoria","descripcion","cantidad","um","precio_proveedor","moneda","iva_incl","margen_opc"])
    calc = calcular(df_items.copy(), p, data["margenes"])
    subtotal_ars = float(calc["total_ars"].sum()) if not calc.empty else 0.0
    iva_monto = subtotal_ars * (float(p["iva"])/100)
    total_c_iva = subtotal_ars + iva_monto

    st.write("*Cliente:*", c.get("cliente",""))
    st.write("*Obra:*", c.get("obra",""))
    st.write("*Arquitecto:*", c.get("arquitecto",""))
    st.write("*Contacto:*", c.get("contacto",""))
    st.write("---")
    st.write("*Totales*")
    st.write(f"Subtotal (ARS): $ {subtotal_ars:,.2f}")
    st.write(f"IVA: $ {iva_monto:,.2f}")
    st.write(f"Total c/IVA (ARS): $ {total_c_iva:,.2f}")

    if st.button("Generar PDF"):
        buffer = BytesIO()
        cpdf = canvas.Canvas(buffer, pagesize=A4)
        W, H = A4
        x, y = 20*mm, H-20*mm
        # header con logo
        try:
            logo = ImageReader(logo_path)
            cpdf.drawImage(logo, x, y-10*mm, width=35*mm, height=15*mm, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
        cpdf.setFont("Helvetica-Bold", 16); cpdf.drawString(x+140, y-2*mm, "NUGENSER — PRESUPUESTO")
        cpdf.setFont("Helvetica", 10); y -= 18*mm
        cpdf.drawString(x, y, f"Cliente: {c.get('cliente','')}"); y -= 5*mm
        cpdf.drawString(x, y, f"Obra: {c.get('obra','')}"); y -= 5*mm
        cpdf.drawString(x, y, f"Arquitecto: {c.get('arquitecto','')}"); y -= 5*mm
        cpdf.drawString(x, y, f"Contacto: {c.get('contacto','')}"); y -= 6*mm
        cpdf.drawString(x, y, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")
        y -= 10*mm; cpdf.setFont("Helvetica-Bold", 11); cpdf.drawString(x, y, "Totales (ARS)")
        cpdf.setFont("Helvetica", 10); y -= 6*mm
        cpdf.drawString(x, y, f"Subtotal: $ {subtotal_ars:,.2f}"); y -= 5*mm
        cpdf.drawString(x, y, f"IVA ({p['iva']}%): $ {iva_monto:,.2f}"); y -= 5*mm
        cpdf.drawString(x, y, f"Total c/IVA: $ {total_c_iva:,.2f}")
        y -= 12*mm; cpdf.setFont("Helvetica", 9)
        tech = ('EL PRESUPUESTO ESTÁ EXPRESADO EN LA MONEDA INDICADA. TIPO DE CAMBIO: "Dólar venta Banco Nación" si corresponde. '
                'EL PRESUPUESTO NO INCLUYE IVA salvo que se indique lo contrario. Las aberturas se fabrican con materiales de alta prestación '
                '(REHAU / ALCEMAR según corresponda) y herrajes de calidad. Los vidrios se seleccionan según IRAM 12565 (espesor) e IRAM 12595 '
                '(zonas de riesgo). En caso de requerir grúa para izaje, el costo será a cargo del cliente.')
        for line in tech.split(". "):
            cpdf.drawString(x, y, line); y -= 5*mm
            if y < 20*mm:
                cpdf.showPage(); y = H-20*mm; cpdf.setFont("Helvetica", 9)
        cpdf.showPage(); cpdf.save(); buffer.seek(0)
        st.download_button("Descargar PDF", data=buffer, file_name="Presupuesto_NUGENSER.pdf", mime="application/pdf")
