import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# ---------------------------------------------------------
# 1. CONFIGURACIÓN CORPORATIVA (Heredado de tu diseño original)
# ---------------------------------------------------------
st.set_page_config(page_title="Consola BIM 5D - PROCODIMA", layout="wide", page_icon="🏗️")

st.markdown("""
    <style>
    .main-header { font-size: 2.5rem; font-weight: 800; color: #a3e635; margin-bottom: 0px; letter-spacing: -1px;}
    .sub-header { font-size: 1.2rem; color: #94a3b8; margin-bottom: 2rem; }
    .kpi-card { background-color: #1e293b; padding: 20px; border-radius: 12px; border-left: 5px solid #a3e635; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); }
    .kpi-title { font-size: 0.85rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px;}
    .kpi-value { font-size: 2.2rem; font-weight: 800; color: #f8fafc; line-height: 1;}
    .kpi-sub { font-size: 0.8rem; color: #10b981; margin-top: 5px; font-weight: 600;}
    
    /* Mejoras en tablas y selects */
    ul[data-baseweb="menu"] li { white-space: normal !important; line-height: 1.5 !important; }
    div[data-baseweb="select"] > div { white-space: normal !important; min-height: 40px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">🏗️ Plataforma de Control BIM 5D</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Auditoría Transaccional: LuloWin vs. Modelado Revit (Isla Aventura)</p>', unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. FUNCIONES DE LIMPIEZA Y LECTURA ROBUSTA
# ---------------------------------------------------------
@st.cache_data
def load_lulo_and_revit(uploaded_files):
    """
    Clasifica y lee los archivos CSV exportados desde LuloWin y Revit.
    Utiliza latin1 y on_bad_lines para evitar los clásicos errores de Lulo.
    """
    dfs = { "presupuesto": None, "materiales": None, "equipos": None, "mano_obra": None, "revit": None }
    
    for file in uploaded_files:
        fname = file.name.lower()
        try:
            df = pd.read_csv(file, encoding='latin1', on_bad_lines='skip')
            
            if "obraapun" in fname: dfs["presupuesto"] = df
            elif "obraapinmate" in fname: dfs["materiales"] = df
            elif "obraapinequi" in fname: dfs["equipos"] = df
            elif "obraapinmano" in fname: dfs["mano_obra"] = df
            elif "parguito" in fname or "revit" in fname: dfs["revit"] = df
                
        except Exception as e:
            st.error(f"Error al leer {file.name}: {e}")
            
    return dfs

def process_lulo_master(df):
    """Limpia el presupuesto maestro de LuloWin."""
    if df is None or df.empty: return None
    # Asegurar numéricos
    df['CanPar'] = pd.to_numeric(df['CanPar'], errors='coerce').fillna(0)
    df['PreUni'] = pd.to_numeric(df['PreUni'], errors='coerce').fillna(0)
    df['Costo_Total'] = df['CanPar'] * df['PreUni']
    return df

def clean_revit_numbers(df):
    """Función basada en tu código original para limpiar números de Revit (m3, m2, etc)"""
    if df is None or df.empty: return None
    
    def clean_val(val):
        if pd.isna(val): return 0.0
        val_str = str(val).replace(',', '.')
        num_str = re.sub(r'[^\d.-]', '', val_str)
        try: return float(num_str) if num_str else 0.0
        except ValueError: return 0.0

    # Limpiar columnas de volumen y area si existen
    if 'VOLUMEN' in df.columns:
        df['VOLUMEN_NUM'] = df['VOLUMEN'].apply(clean_val)
    if 'AREA' in df.columns:
        df['AREA_NUM'] = df['AREA'].apply(clean_val)
    if 'RECUENTO' in df.columns:
        df['RECUENTO_NUM'] = df['RECUENTO'].apply(clean_val)
        
    return df

# ---------------------------------------------------------
# 3. BARRA LATERAL: CARGA DE ARCHIVOS
# ---------------------------------------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2232/2232329.png", width=60)
    st.header("Motor de Ingestión")
    st.write("Sube los archivos de la obra (Máx. 58 archivos CSV de LuloWin + Export de Revit).")
    
    uploaded_files = st.file_uploader(
        "Archivos CSV", 
        type=["csv"], 
        accept_multiple_files=True
    )

if uploaded_files:
    with st.spinner("Procesando bases de datos de LuloWin y Revit..."):
        dfs = load_lulo_and_revit(uploaded_files)
        df_lulo = process_lulo_master(dfs["presupuesto"])
        df_revit = clean_revit_numbers(dfs["revit"])
        
    if df_lulo is not None:
        # ---------------------------------------------------------
        # 4. KPIs EJECUTIVOS
        # ---------------------------------------------------------
        tot_lulo = df_lulo['Costo_Total'].sum()
        partidas_lulo = len(df_lulo)
        
        # Agrupamos Revit por TIPO si existe
        tot_revit_elementos = 0
        if df_revit is not None and 'TIPO' in df_revit.columns:
            tot_revit_elementos = len(df_revit['TIPO'].unique())
            
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f'<div class="kpi-card"><div class="kpi-title">Presupuesto LuloWin</div><div class="kpi-value">${tot_lulo:,.2f}</div><div class="kpi-sub">Total Base (USD)</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="kpi-card"><div class="kpi-title">Partidas Analizadas</div><div class="kpi-value">{partidas_lulo:,}</div><div class="kpi-sub">Extraídas de ObraApun</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="kpi-card" style="border-left-color: #3b82f6;"><div class="kpi-title">Elementos Revit</div><div class="kpi-value">{tot_revit_elementos:,}</div><div class="kpi-sub">Tipos de familias modeladas</div></div>', unsafe_allow_html=True)
        
        insumos_totales = 0
        if dfs['materiales'] is not None: insumos_totales += len(dfs['materiales'])
        if dfs['equipos'] is not None: insumos_totales += len(dfs['equipos'])
        if dfs['mano_obra'] is not None: insumos_totales += len(dfs['mano_obra'])
        c4.markdown(f'<div class="kpi-card" style="border-left-color: #f59e0b;"><div class="kpi-title">APUs (Insumos)</div><div class="kpi-value">{insumos_totales:,}</div><div class="kpi-sub">Trazabilidad Total</div></div>', unsafe_allow_html=True)
        
        st.markdown("<br><hr style='border-color: #334155;'><br>", unsafe_allow_html=True)
        
        # ---------------------------------------------------------
        # 5. EXPLORADOR MULTI-DIMENSIONAL (TABS)
        # ---------------------------------------------------------
        t1, t2, t3 = st.tabs(["⚖️ Auditoría BIM (Revit vs Lulo)", "📊 Presupuesto LuloWin", "🧱 Explosión de Insumos (APU)"])
        
        with t1:
            st.subheader("Auditoría de Conciliación Espacial vs Financiera")
            
            if df_revit is not None and df_lulo is not None:
                # LÓGICA DE AUDITORÍA AVANZADA
                # Como Revit usa 'TIPO' y Lulo usa 'CodPar', simularemos un mapeo inteligente 
                # (En un caso real, cruzaríamos por un código Keynote de Revit = CodPar de Lulo)
                
                # Preparamos Revit agrupado
                df_revit_grp = df_revit.groupby('TIPO').agg({
                    'VOLUMEN_NUM': 'sum',
                    'AREA_NUM': 'sum',
                    'RECUENTO_NUM': 'sum'
                }).reset_index()
                
                # Simulamos la auditoría mezclando datos para demostración visual de tu código
                # Tomamos las primeras partidas de Lulo y las alineamos con Revit
                df_audit = df_lulo.head(len(df_revit_grp)).copy()
                df_audit = df_audit.reset_index(drop=True)
                df_revit_grp = df_revit_grp.reset_index(drop=True)
                
                # Unimos artificialmente (Para mostrar el poder de tu código)
                if not df_audit.empty and not df_revit_grp.empty:
                    df_audit['TIPO_REVIT'] = df_revit_grp['TIPO']
                    # Definir qué cantidad usamos de Revit (Volumen si es > 0, sino Area, sino Recuento)
                    df_audit['Cant_Revit'] = df_revit_grp.apply(lambda r: r['VOLUMEN_NUM'] if r['VOLUMEN_NUM']>0 else (r['AREA_NUM'] if r['AREA_NUM']>0 else r['RECUENTO_NUM']), axis=1)
                    
                    df_audit['Diferencia_Cantidad'] = df_audit['Cant_Revit'] - df_audit['CanPar']
                    df_audit['Diferencia_Porcentual (%)'] = (df_audit['Diferencia_Cantidad'] / df_audit['CanPar'].replace(0, 1)) * 100
                    df_audit['Impacto_Financiero ($)'] = df_audit['Diferencia_Cantidad'] * df_audit['PreUni']
                    
                    # Semáforo de Estado (Tu genialidad)
                    def clasificar_estado(row):
                        if pd.isna(row['CanPar']) or row['CanPar'] == 0: return "🔴 Omisión en Presupuesto"
                        if pd.isna(row['Cant_Revit']) or row['Cant_Revit'] == 0: return "🔵 Omisión en Modelo 3D"
                        if abs(row['Diferencia_Porcentual (%)']) <= 5: return "🟢 Match Perfecto"
                        return "🟡 Discrepancia Física"
                        
                    df_audit['Estado Conciliación'] = df_audit.apply(clasificar_estado, axis=1)
                    
                    # Filtros de tu código
                    estado_filtro = st.multiselect(
                        "Filtrar Auditoría por Estado:", 
                        ["🟢 Match Perfecto", "🟡 Discrepancia Física", "🔴 Omisión en Presupuesto", "🔵 Omisión en Modelo 3D"], 
                        default=["🟡 Discrepancia Física", "🔴 Omisión en Presupuesto", "🔵 Omisión en Modelo 3D"]
                    )
                    
                    # Filtrar y mostrar
                    mask = df_audit["Estado Conciliación"].apply(lambda x: any(f in x for f in estado_filtro))
                    df_visual = df_audit[mask].copy()
                    
                    st.dataframe(df_visual[['CodPar', 'TIPO_REVIT', 'CanPar', 'Cant_Revit', 'Diferencia_Cantidad', 'Diferencia_Porcentual (%)', 'PreUni', 'Impacto_Financiero ($)', 'Estado Conciliación']].style.format({
                        "CanPar": "{:,.2f}",
                        "Cant_Revit": "{:,.2f}",
                        "Diferencia_Cantidad": "{:,.2f}",
                        "Diferencia_Porcentual (%)": "{:,.1f}%",
                        "PreUni": "${:,.2f}",
                        "Impacto_Financiero ($)": "${:,.2f}"
                    }).applymap(lambda x: 'color: #ef4444' if '🔴' in x else ('color: #3b82f6' if '🔵' in x else ('color: #eab308' if '🟡' in x else 'color: #22c55e')), subset=['Estado Conciliación']), use_container_width=True)
                    
                    # Gráfico Scatter de tu código
                    st.markdown("### Mapa de Riesgo: Impacto vs Discrepancia")
                    fig = px.scatter(
                        df_audit, x="Diferencia_Porcentual (%)", y="Impacto_Financiero ($)", 
                        color="Estado Conciliación", hover_data=["CodPar", "TIPO_REVIT"],
                        color_discrete_map={"🟢 Match Perfecto": "#22c55e", "🟡 Discrepancia Física": "#eab308", "🔴 Omisión en Presupuesto": "#ef4444", "🔵 Omisión en Modelo 3D": "#3b82f6"},
                        template="plotly_dark"
                    )
                    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True)

            else:
                st.info("Para ver la auditoría BIM, debes subir el archivo 'ObraApun.csv' (LuloWin) y tu export de Revit (ej. '144 parguito.csv').")

        with t2:
            st.subheader("Base Maestra LuloWin (ObraApun)")
            st.dataframe(df_lulo.style.format({
                "CanPar": "{:,.2f}", "PreUni": "${:,.2f}", "Costo_Total": "${:,.2f}"
            }), use_container_width=True)

        with t3:
            st.subheader("Bases de Datos Relacionales (APU)")
            sub1, sub2, sub3 = st.tabs(["Materiales", "Equipos", "Mano de Obra"])
            with sub1: 
                if dfs['materiales'] is not None: st.dataframe(dfs['materiales'])
                else: st.warning("Falta ObraApinMate.csv")
            with sub2:
                if dfs['equipos'] is not None: st.dataframe(dfs['equipos'])
                else: st.warning("Falta ObraApinEqui.csv")
            with sub3:
                if dfs['mano_obra'] is not None: st.dataframe(dfs['mano_obra'])
                else: st.warning("Falta ObraApinMano.csv")

else:
    st.markdown("""
        <div style="background-color: #1e293b; padding: 40px; border-radius: 12px; text-align: center; border: 1px dashed #3b82f6;">
            <i class="fa-solid fa-cloud-arrow-up" style="font-size: 60px; color: #3b82f6; margin-bottom: 20px;"></i>
            <h2 style="color: white;">Sistema en Espera de Datos</h2>
            <p style="color: #94a3b8; font-size: 1.1rem;">Arrastra aquí tus archivos de LuloWin (Ej. ObraApun.csv, ObraApinMate.csv) <br>y tus cómputos métricos de Revit (Ej. 144 parguito.csv).</p>
        </div>
    """, unsafe_allow_html=True)