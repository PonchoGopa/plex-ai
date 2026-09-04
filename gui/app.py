import sys
import os
import platform
import subprocess
from pathlib import Path
import streamlit as st

# Asegurar que el directorio raíz está en el path de búsqueda de módulos
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from api.pipeline import run_pipeline

# Configuración de página
st.set_page_config(
    page_title="KI USA - Plex ERP Importer",
    page_icon="assets/logo.png" if Path("assets/logo.png").exists() else "📂",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Estilos CSS para el diseño "Liquid Glass" (Glassmorphism)
GLASS_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

/* Variables CSS de Streamlit para forzar paleta clara en todos los componentes */
:root {
    --background-color: #f8fafc !important;
    --secondary-background-color: #ffffff !important;
    --text-color: #0f172a !important;
    --primary-color: #4f46e5 !important;
}

/* Fondo general de la aplicación con degradado claro */
.stApp {
    background: linear-gradient(135deg, #f8fafc 0%, #e0e7ff 50%, #f1f5f9 100%) !important;
    background-attachment: fixed !important;
    color: #1e293b !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Ocultar barra superior por defecto de streamlit */
header {
    background: transparent !important;
}

/* Contenedor principal con efecto vidrio esmerilado claro */
.block-container {
    background: rgba(255, 255, 255, 0.65) !important;
    backdrop-filter: blur(25px) saturate(160%) !important;
    -webkit-backdrop-filter: blur(25px) saturate(160%) !important;
    border: 1px solid rgba(255, 255, 255, 0.8) !important;
    border-radius: 24px !important;
    padding: 3.5rem !important;
    max-width: 780px !important;
    margin-top: 4rem !important;
    margin-bottom: 4rem !important;
    box-shadow: 0 20px 50px rgba(15, 23, 42, 0.08) !important;
}

/* Modificaciones a los títulos de Streamlit */
h1, h2, h3, h4, h5, h6 {
    color: #0f172a !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}

/* Estilización del File Uploader */
[data-testid="stFileUploader"] {
    background: rgba(255, 255, 255, 0.7) !important;
    border: 1px dashed rgba(79, 70, 229, 0.3) !important;
    border-radius: 16px !important;
    padding: 24px !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
[data-testid="stFileUploader"]:hover {
    border-color: #4f46e5 !important;
    background: rgba(255, 255, 255, 0.9) !important;
    box-shadow: 0 0 20px rgba(99, 102, 241, 0.1);
}

/* Sub-elementos del File Uploader (Dropzone y archivo cargado) */
[data-testid="stFileUploader"] section {
    background: rgba(255, 255, 255, 0.7) !important;
    border-radius: 12px !important;
}
[data-testid="stFileUploader"] ul,
[data-testid="stFileUploader"] li,
[data-testid="stFileUploaderFile"],
[data-testid="stFileUploaderFileData"],
[data-testid="stFileUploader"] div[role="listitem"] {
    background: #ffffff !important;
    color: #0f172a !important;
    border: 1px solid rgba(15, 23, 42, 0.12) !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04) !important;
}
[data-testid="stFileUploader"] * {
    color: #1e293b !important;
}
[data-testid="stFileUploader"] small {
    color: #64748b !important;
}
[data-testid="stFileUploader"] svg {
    fill: #475569 !important;
    color: #475569 !important;
}

/* TODOS los botones: stButton, stDownloadButton, etc. en blanco brillante y texto oscuro nítido */
.stButton > button,
.stDownloadButton > button,
button[kind="secondary"],
button[kind="primary"],
[data-testid="baseButton-secondary"],
[data-testid="baseButton-primary"],
[data-testid="stFileUploaderDropzone"] button {
    background: #ffffff !important;
    color: #0f172a !important;
    border: 1px solid rgba(15, 23, 42, 0.15) !important;
    border-radius: 12px !important;
    padding: 0.65rem 2rem !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.05) !important;
    transition: all 0.25s ease !important;
    width: 100% !important;
}

/* Forzar textos e iconos dentro de los botones a ser oscuros y visibles */
.stButton > button *,
.stDownloadButton > button *,
button[kind="secondary"] *,
button[kind="primary"] *,
[data-testid="baseButton-secondary"] *,
[data-testid="baseButton-primary"] *,
[data-testid="stFileUploaderDropzone"] button * {
    color: #0f172a !important;
    fill: #0f172a !important;
    font-weight: 600 !important;
}

/* Hover de los botones */
.stButton > button:hover,
.stDownloadButton > button:hover,
button[kind="secondary"]:hover,
button[kind="primary"]:hover,
[data-testid="baseButton-secondary"]:hover,
[data-testid="baseButton-primary"]:hover,
[data-testid="stFileUploaderDropzone"] button:hover {
    background: #f8fafc !important;
    border-color: #4f46e5 !important;
    box-shadow: 0 4px 16px rgba(79, 70, 229, 0.15) !important;
    transform: translateY(-1px) !important;
}

.stButton > button:hover *,
.stDownloadButton > button:hover *,
button[kind="secondary"]:hover *,
button[kind="primary"]:hover * {
    color: #4f46e5 !important;
    fill: #4f46e5 !important;
}

.stButton > button:active,
.stDownloadButton > button:active,
button:active {
    transform: translateY(1px) !important;
}

/* Estilo para las alertas y cuadros de mensaje */
.glass-alert {
    background: rgba(255, 255, 255, 0.7) !important;
    border-radius: 12px !important;
    border-left: 4px solid #4f46e5 !important;
    padding: 16px !important;
    margin-bottom: 20px !important;
    backdrop-filter: blur(8px) !important;
    color: #0f172a !important;
}
.glass-success {
    background: rgba(236, 253, 245, 0.85) !important;
    border: 1px solid rgba(16, 185, 129, 0.3) !important;
    border-left: 5px solid #10b981 !important;
    border-radius: 12px !important;
    padding: 18px !important;
    margin-bottom: 20px !important;
    backdrop-filter: blur(8px) !important;
    color: #065f46 !important;
}
.glass-error {
    background: rgba(254, 242, 242, 0.85) !important;
    border: 1px solid rgba(239, 68, 68, 0.3) !important;
    border-left: 5px solid #ef4444 !important;
    border-radius: 12px !important;
    padding: 18px !important;
    margin-bottom: 20px !important;
    backdrop-filter: blur(8px) !important;
    color: #991b1b !important;
}

/* Estilo de los expanders de Streamlit */
[data-testid="stExpander"],
.streamlit-expanderHeader {
    background: #ffffff !important;
    border: 1px solid rgba(15, 23, 42, 0.12) !important;
    border-radius: 12px !important;
    color: #0f172a !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.02) !important;
    margin-bottom: 10px !important;
}
[data-testid="stExpander"] summary,
.streamlit-expanderHeader {
    background: #ffffff !important;
    color: #0f172a !important;
    font-weight: 600 !important;
}
[data-testid="stExpander"] summary:hover {
    color: #4f46e5 !important;
}
[data-testid="stExpander"] summary * {
    color: #0f172a !important;
    fill: #0f172a !important;
}
[data-testid="stExpanderDetails"],
.streamlit-expanderContent {
    background: #f8fafc !important;
    border: 1px solid rgba(15, 23, 42, 0.08) !important;
    border-top: none !important;
    border-radius: 0 0 12px 12px !important;
    color: #0f172a !important;
}
</style>
"""

st.markdown(GLASS_CSS, unsafe_allow_html=True)

# ── CABECERA DE LA APLICACIÓN ─────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 4])

with col_logo:
    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        st.image(str(logo_path), use_container_width=True)
    else:
        st.write("### KI USA")

with col_title:
    st.markdown(
        """
        <div style="margin-top: 5px;">
            <h1 style="margin: 0; font-size: 2.2rem; font-weight: 700; background: linear-gradient(to right, #0f172a, #475569); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                Plex ERP Importer
            </h1>
            <p style="margin: 3px 0 0 0; color: #475569; font-size: 0.95rem; font-weight: 400;">
                Extractor y Validador de Órdenes de Compra (PDF / Excel)
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<hr style='border: 0; border-top: 1px solid rgba(15, 23, 42, 0.08); margin: 2rem 0;'>", unsafe_allow_html=True)

# ── CARGA DE ARCHIVO ─────────────────────────────────────────────────────────
st.markdown("### 📥 Cargar Documento")
uploaded_file = st.file_uploader(
    "Selecciona o arrastra un archivo PDF o Excel",
    type=["pdf", "xlsx", "xls"],
    help="Soporta PDFs de Topre, Y-tec y archivos Excel de S-Riko.",
)

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    file_name = uploaded_file.name

    st.markdown("<br>", unsafe_allow_html=True)
    
    with st.spinner("Procesando documento y generando archivos XML..."):
        try:
            # Ejecutar el pipeline
            zip_bytes, info = run_pipeline(
                pdf_bytes=file_bytes,
                pdf_filename=file_name,
                out_base="output",
            )
            
            # Obtener carpeta física final
            po_number = info["po_number"] or "UNKNOWN"
            abs_out_dir = Path("output").resolve() / po_number
            
            # Mostrar resultado exitoso
            st.markdown(
                f"""
                <div class="glass-success">
                    <h4 style="margin: 0 0 8px 0; color: #10b981;">🎉 Documento procesado con éxito</h4>
                    <table style="width:100%; border-collapse: collapse; font-size: 0.9rem; color: #334155; margin-top: 10px;">
                        <tr>
                            <td style="padding: 4px 0; font-weight: 600;">Cliente Code:</td>
                            <td>{info['customer']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; font-weight: 600;">Orden de Compra (PO):</td>
                            <td>{info['po_number']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; font-weight: 600;">Registros procesados:</td>
                            <td>{info['records']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; font-weight: 600;">Advertencias:</td>
                            <td>{info['warnings']} {('⚠️' if info['warnings'] > 0 else '✅')}</td>
                        </tr>
                    </table>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Botones de Acción
            st.markdown("### 🛠️ Acciones")
            
            # Botón 1: Abrir carpeta física local en explorador
            if st.button("📂 Abrir carpeta en Explorador"):
                try:
                    if platform.system() == "Windows":
                        os.startfile(str(abs_out_dir))
                    elif platform.system() == "Darwin":  # macOS
                        subprocess.run(["open", str(abs_out_dir)])
                    else:  # Linux
                        subprocess.run(["xdg-open", str(abs_out_dir)])
                    st.toast("¡Carpeta abierta en el explorador!", icon="📂")
                except Exception as e:
                    st.error(f"No se pudo abrir la carpeta automáticamente: {e}")
                    
            # Mostrar la ruta en texto plano
            st.markdown(
                f"""
                <div style="font-size: 0.85rem; color: #475569; background: rgba(15, 23, 42, 0.03); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(15, 23, 42, 0.05); margin-top:-10px; margin-bottom:15px; font-family: monospace; word-break: break-all;">
                    Ruta física: {abs_out_dir}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Botón 2: Descargar ZIP
            st.download_button(
                label="📥 Descargar todos los XMLs (.zip)",
                data=zip_bytes,
                file_name=f"{po_number}_plex_import.zip",
                mime="application/zip",
            )
            
            # Mostrar archivos XML generados
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### 📄 Archivos XML Generados")
            for file_path_str in info["generated_files"]:
                p = Path(file_path_str)
                if p.exists():
                    with st.expander(f"XML: {p.name}"):
                        try:
                            xml_content = p.read_text(encoding="utf-8")
                            st.code(xml_content, language="xml")
                        except Exception as e:
                            st.error(f"Error al leer el archivo {p.name}: {e}")
                else:
                    st.warning(f"No se encontró el archivo: {p.name}")

        except ValueError as val_err:
            # Capturar errores de validación arrojados por el pipeline
            err_msg_html = str(val_err).replace('\n', '<br>')
            st.markdown(
                f"""
                <div class="glass-error">
                    <h4 style="margin: 0 0 8px 0; color: #ef4444;">❌ Generación Bloqueada</h4>
                    <p style="margin: 0; font-size: 0.95rem; line-height: 1.5; color: #991b1b;">
                        {err_msg_html}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as exc:
            # Capturar cualquier otro error inesperado
            st.markdown(
                f"""
                <div class="glass-error">
                    <h4 style="margin: 0 0 8px 0; color: #ef4444;">💥 Error inesperado</h4>
                    <p style="margin: 0; font-size: 0.95rem; color: #991b1b;">
                        {exc}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    # Estado inicial: Sin archivos cargados
    st.markdown(
        """
        <div style="text-align: center; color: #64748b; padding: 3rem 1rem;">
            <p style="margin: 0; font-size: 1.1rem;">Arrastre y suelte su archivo PDF o Excel arriba para comenzar.</p>
            <p style="margin: 5px 0 0 0; font-size: 0.85rem;">Soporta facturas/planificaciones de Topre, Y-tec y S-Riko.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
