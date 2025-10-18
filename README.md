# NUGENSER • Presupuestos (Web)
App web con login (Julieta / Cacho), branding NUGENSER y generación de PDF.

## Deploy rápido en Streamlit Cloud
1) Crear un repo nuevo en GitHub (por ejemplo `nugenser-presupuestos-app`).
2) Subir estos archivos tal cual (mantener la carpeta `assets/`):
   - `app.py`
   - `requirements.txt`
   - `assets/logo.png`
3) En https://streamlit.io → **Sign in** → **Deploy app**. Apuntar a `app.py`.
4) (Opcional) En **Secrets** agregá:
   ```toml
   JULIETA_PASS="tu_clave_secreta"
   CACHO_PASS="tu_clave_secreta"
   ```
   Si no seteás secrets, ambas contraseñas por defecto son **demo** para probar.

## Uso
- Usuario: **Julieta** o **Cacho** (según el login)
- Cargá ítems de proveedores: Proveedor, Categoría, Descripción, Cantidad, UM, Precio, Moneda, ¿IVA incl.? (S/N), Margen % opcional.
- Configurá **Tipo de Cambio**, **IVA**, **Margen global** y **Márgenes por proveedor/categoría**.
- Exportá el **PDF** con branding NUGENSER y notas técnicas (IRAM 12565/12595, grúa).
