
import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import json, os
from datetime import datetime

st.set_page_config(page_title="NUGENSER • Presupuestos", page_icon="🧱", layout="wide")

# ---------- Login simple (demo) ----------
def check_login(user, pwd):
    env_pwd = os.environ.get(f"{user.upper()}_PASS")
    demo_pwd = "demo"
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

# ---------- Datos base ----------
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
        margen = float(margen_linea) if (margen_linea not in (None,"")) else margin_lookup(margenes, proveedor, categoria, float(params["margen_global"]))
        neto_sin_iva = pu_prov / (1+float(params["iva"])/100) if iva_incl else pu_prov
        pu_margen = neto_sin_iva * (1 + margen/100)
        total_moneda = pu_margen * cant
        tc = float(params["tc"]) if moneda == "USD" else 1.0
        rows.append({
            **row,
            "neto_sin_iva": round(neto_sin_iva,2),
            "margen_usado_%": round(margen,2),
            "pu_margen": round(pu_margen,2),
            "total_moneda": round(total_moneda,2),
            "tc_usado": tc,
            "total_ars": round(total_moneda*tc,2),
        })
    return pd.DataFrame(rows)

data = load_data()
st.sidebar.write(f"👤 {st.session_state.user}")
page = st.sidebar.radio("Navegación", ["Presupuesto", "Config", "Exportar PDF"])

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

else:
    st.header("Exportar PDF")
    st.caption("Genera un PDF con carátula, totales e información técnica IRAM 12565/12595.")
    c = data["cliente"]; p = data["params"]
    df_items = pd.DataFrame(data["items"] or [], columns=["proveedor","categoria","descripcion","cantidad","um","precio_proveedor","moneda","iva_incl","margen_opc"])
    calc = calcular(df_items.copy(), p, data["margenes"])
    subtotal_ars = float(calc["total_ars"].sum()) if not calc.empty else 0.0
    iva_monto = subtotal_ars * (float(p["iva"])/100)
    total_c_iva = subtotal_ars + iva_monto

    st.write("**Cliente:**", c.get("cliente",""))
    st.write("**Obra:**", c.get("obra",""))
    st.write("**Arquitecto:**", c.get("arquitecto",""))
    st.write("**Contacto:**", c.get("contacto",""))
    st.write("---")
    st.write("**Totales**")
    st.write(f"Subtotal (ARS): $ {subtotal_ars:,.2f}")
    st.write(f"IVA: $ {iva_monto:,.2f}")
    st.write(f"Total c/IVA (ARS): $ {total_c_iva:,.2f}")

    if st.button("Generar PDF"):
        buffer = BytesIO()
        cpdf = canvas.Canvas(buffer, pagesize=A4)
        W, H = A4
        x, y = 20*mm, H-20*mm
        # header with logo
        try:
            from reportlab.lib.utils import ImageReader
            logo = ImageReader(logo_path)
            cpdf.drawImage(logo, x, y-10*mm, width=35*mm, height=15*mm, preserveAspectRatio=True, mask='auto')
        except Exception as e:
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
