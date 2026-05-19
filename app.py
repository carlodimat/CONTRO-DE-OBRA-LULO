import streamlit as st
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
import re
import io

# Configuración de diseño corporativo de alta gama
st.set_page_config(page_title="Consola de Control Financiero - Lulo", layout="wide")

# Inyección de CSS para mejorar la legibilidad y forzar saltos de línea en selectores
st.markdown("""
    <style>
    /* Forzar ajuste de texto en las opciones desplegables */
    ul[data-baseweb="menu"] li {
        white-space: normal !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        line-height: 1.5 !important;
        padding-top: 8px !important;
        padding-bottom: 8px !important;
        border-bottom: 1px solid #f0f2f6;
    }
    /* Forzar ajuste de texto en la caja seleccionada */
    div[data-baseweb="select"] > div {
        white-space: normal !important;
        word-wrap: break-word !important;
        height: auto !important;
        min-height: 40px;
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIÓN ROBUSTA PARA LIMPIAR Y CONVERTIR NÚMEROS CON UNIDADES (m³, m², kg, ml, etc.) ---
def clean_numeric_value(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    if not val_str:
        return 0.0
    
    # Extraer estrictamente números del 0-9, decimales y negativos
    cleaned = ""
    for char in val_str:
        if char in '0123456789.,-':
            cleaned += char
            
    if not cleaned:
        return 0.0
    
    # Detectar y corregir formatos regionales de millar y decimal
    dot_count = cleaned.count('.')
    comma_count = cleaned.count(',')
    
    if dot_count > 0 and comma_count > 0:
        if cleaned.rfind('.') > cleaned.rfind(','):
            cleaned = cleaned.replace(',', '')  
        else:
            cleaned = cleaned.replace('.', '').replace(',', '.')  
    elif comma_count > 0:
        parts = cleaned.split(',')
        if len(parts) == 2:
            if len(parts[1]) == 3 and float(parts[0]) > 0:
                cleaned = cleaned.replace(',', '')  
            else:
                cleaned = cleaned.replace(',', '.')  
        else:
            cleaned = cleaned.replace(',', '')  
    elif dot_count > 1:
        cleaned = cleaned.replace('.', '')  
        
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

# --- MOTOR DE LECTURA DIRECTA MATEMÁTICO ---
def load_csv_robustly(file_buffer):
    if file_buffer is None:
        return None
    try:
        raw_data = file_buffer.getvalue()
        
        decoded_text = None
        encodings = ['utf-8', 'utf-16', 'latin1', 'cp1252']
        if b'\x00' in raw_data or raw_data.startswith(b'\xff\xfe') or raw_data.startswith(b'\xfe\xff'):
            encodings = ['utf-16', 'utf-8', 'latin1', 'cp1252']
            
        for enc in encodings:
            try:
                decoded_text = raw_data.decode(enc).replace('\x00', '')
                break
            except Exception:
                continue
                
        if not decoded_text:
            decoded_text = raw_data.decode('utf-8', errors='ignore')
            
        first_lines = "\n".join(decoded_text.split('\n')[:20])
        separators = [',', ';', '\t']
        sep_counts = {sep: first_lines.count(sep) for sep in separators}
        best_sep = max(sep_counts, key=sep_counts.get)
        if sep_counts[best_sep] == 0:
            best_sep = ','
            
        try:
            df = pd.read_csv(io.StringIO(decoded_text), sep=best_sep, on_bad_lines='skip', quotechar='"')
        except Exception:
            df = pd.read_csv(io.StringIO(decoded_text), sep=best_sep, engine='python', on_bad_lines='skip', quotechar='"')
        
        if df is None or df.empty:
            return None
            
        df = df.copy()
        
        unnamed_count = sum(1 for c in df.columns if "unnamed" in str(c).lower())
        if unnamed_count >= len(df.columns) / 2 and len(df) > 0:
            new_header = df.iloc[0].astype(str)
            df = df[1:].copy()
            df.columns = [f"Col_{i}" for i in range(len(df.columns))] 
            
        keep_indices = []
        new_names = []
        for i in range(len(df.columns)):
            col_str = str(df.columns[i]).strip()
            if "unnamed" in col_str.lower() or col_str.lower() in ['nan', 'none', '']:
                if df.iloc[:, i].notna().sum() > 0: 
                    keep_indices.append(i)
                    new_names.append(f"Col_Extra_{i+1}")
            else:
                keep_indices.append(i)
                new_names.append(col_str)
                
        df = df.iloc[:, keep_indices].copy()
        
        seen = {}
        unique_cols = []
        for col in new_names:
            if not col or col.lower() == 'nan':
                col = "Columna"
            if col in seen:
                seen[col] += 1
                unique_cols.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                unique_cols.append(col)
                
        df.columns = unique_cols
        df = df.dropna(how='all')
        
        def is_valid_row(row):
            row_str = " ".join(row.astype(str).fillna("")).lower()
            if "total" in row_str or "suma" in row_str or "grand total" in row_str:
                return False
            return True
            
        df = df[df.apply(is_valid_row, axis=1)]
        df = df.reset_index(drop=True)
        
        return df
        
    except Exception as e:
        st.error(f"Error procesando el archivo CSV: {str(e)}")
        return None

# --- ALGORITMO LINGÜÍSTICO ---
def encontrar_mejor_coincidencia(revit_desc, lulo_items):
    if not isinstance(revit_desc, str):
        return "NINGUNA / EXCLUIR"
        
    def normalize(text):
        if not isinstance(text, str):
            return set()
        text = text.lower()
        accents = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'}
        for a, b in accents.items():
            text = text.replace(a, b)
        words = re.findall(r'\w+', text)
        stop_words = {'de', 'para', 'con', 'el', 'la', 'los', 'las', 'un', 'una', 'y', 'en', 'sobre', 'bajo', 'm', 'm2', 'm3', 'kg', 'unid', 'und', 'pzs'}
        return set(w for w in words if w not in stop_words and len(w) > 1)

    revit_tokens = normalize(revit_desc)
    if not revit_tokens:
        return "NINGUNA / EXCLUIR"
        
    best_code = "NINGUNA / EXCLUIR"
    best_score = 0.0
    
    for cod, nom in lulo_items:
        if str(cod).lower() in revit_desc.lower():
            return cod
            
        lulo_tokens = normalize(nom)
        if not lulo_tokens:
            continue
            
        intersection = revit_tokens.intersection(lulo_tokens)
        union = revit_tokens.union(lulo_tokens)
        score = len(intersection) / len(union) if union else 0.0
        
        if score > best_score:
            best_score = score
            best_code = cod
            
    if best_score >= 0.12:
        return best_code
    return "NINGUNA / EXCLUIR"

# --- INICIALIZACIÓN DE VARIABLES DE ESTADO ---
if "revit_raw_df" not in st.session_state:
    st.session_state["revit_raw_df"] = None
if "advanced_mapping" not in st.session_state:
    st.session_state["advanced_mapping"] = {} 
if "modo_cantidades" not in st.session_state:
    st.session_state["modo_cantidades"] = "Original Lulo"
if "no_modelados_cero" not in st.session_state:
    st.session_state["no_modelados_cero"] = False

# --- RADAR GLOBAL DE PROYECTOS ---
def detectar_proyectos():
    proyectos_validos = {}
    if os.path.exists("ObraApun.csv"):
        proyectos_validos["Proyecto Raíz (Principal)"] = "."
    if os.path.exists("Obras"):
        for d in os.listdir("Obras"):
            ruta_completa = os.path.join("Obras", d)
            if os.path.isdir(ruta_completa) and os.path.exists(os.path.join(ruta_completa, "ObraApun.csv")):
                proyectos_validos[d] = ruta_completa
    for d in os.listdir("."):
        if os.path.isdir(d) and d not in ["Obras", ".git", ".streamlit", "__pycache__"]:
            if os.path.exists(os.path.join(d, "ObraApun.csv")):
                proyectos_validos[d] = d
    return proyectos_validos

@st.cache_data
def consolidar_ingenieria_costos_lulo(ruta_proyecto):
    df_presupuesto = pd.read_csv(os.path.join(ruta_proyecto, "ObraApun.csv"))
    df_mat_apu = pd.read_csv(os.path.join(ruta_proyecto, "ObraApinMate.csv"))
    df_mano_apu = pd.read_csv(os.path.join(ruta_proyecto, "ObraApinMano.csv"))
    df_equ_apu = pd.read_csv(os.path.join(ruta_proyecto, "ObraApinEqui.csv"))
    df_capitulos = pd.read_csv(os.path.join(ruta_proyecto, "ObraCapi.csv"))
    df_proyecto = pd.read_csv(os.path.join(ruta_proyecto, "ObraProy.csv")).iloc[0]
    
    df_dict_partidas = pd.read_csv(os.path.join(ruta_proyecto, "ObraPart.csv"))[["CodPar", "Descri", "UniPar"]].rename(columns={"Descri": "NomPar"})
    df_dict_mate = pd.read_csv(os.path.join(ruta_proyecto, "ObraMate.csv"))[["CodMat", "Descri", "UniMat"]].rename(columns={"CodMat": "CodIns", "Descri": "NomIns", "UniMat": "UniIns"})
    df_dict_mano = pd.read_csv(os.path.join(ruta_proyecto, "ObraMano.csv"))[["CodMan", "Descri"]].rename(columns={"CodMan": "CodIns", "Descri": "NomIns"})
    df_dict_mano["UniIns"] = "JORNAL"
    df_dict_equi = pd.read_csv(os.path.join(ruta_proyecto, "ObraEqui.csv"))[["CodEqu", "Descri"]].rename(columns={"CodEqu": "CodIns", "Descri": "NomIns"})
    df_dict_equi["UniIns"] = "DIA"
    
    df_insumos_master = pd.concat([df_dict_mate, df_dict_mano, df_dict_equi], ignore_index=True).drop_duplicates(subset=["CodIns"])
    df_pres_completo = pd.merge(df_presupuesto, df_dict_partidas, on="CodPar", how="left")
    df_pres_completo["NomPar"] = df_pres_completo["NomPar"].fillna(df_pres_completo["CodPar"])
    
    return df_pres_completo, df_mat_apu, df_mano_apu, df_equ_apu, df_capitulos, df_insumos_master, df_proyecto

# --- ESTRUCTURA DEL HUB ---
st.title("📊 Consola Maestra de Control Financiero y Auditoría")

proyectos_dict = detectar_proyectos()

if not proyectos_dict:
    st.info("💡 No se detectaron archivos del presupuesto. Sube las carpetas de Lulo Win a GitHub para empezar.")
else:
    st.sidebar.markdown("### 🌐 Gestión de Portafolio")
    nombres_proyectos = list(proyectos_dict.keys())
    proyecto_seleccionado = st.sidebar.selectbox("Seleccione el Proyecto Activo:", nombres_proyectos)
    st.sidebar.write("---")
    
    try:
        ruta_seleccionada = proyectos_dict[proyecto_seleccionado]
        df_pres, df_mat, df_mano, df_equ, df_cap, df_insumos, df_proy = consolidar_ingenieria_costos_lulo(ruta_seleccionada)
        
        st.sidebar.markdown(f"**Cliente:** {df_proy.get('Propie', 'N/A')}\n\n**Calculista:** {df_proy.get('Calcul', 'N/A')}\n\n**Revisor:** {df_proy.get('Reviso', 'N/A')}")
        st.sidebar.write("---")
        
        conector_listo = st.session_state["revit_raw_df"] is not None and len(st.session_state["advanced_mapping"]) > 0
        if conector_listo:
            st.sidebar.markdown("### 🔌 Conector BIM 5D Activo")
            st.session_state["modo_cantidades"] = st.sidebar.radio(
                "Origen de Cómputos Métricos:",
                ["Original Lulo", "Modelo Revit 3D"]
            )
            st.session_state["no_modelados_cero"] = st.sidebar.checkbox(
                "Llevar a cero (0) partidas no modeladas",
                value=st.session_state["no_modelados_cero"],
                help="Si se activa, las partidas del presupuesto que no estén mapeadas a Revit se calcularán con cantidad cero."
            )
            st.sidebar.write("---")
        else:
            st.session_state["modo_cantidades"] = "Original Lulo"
        
        # --- PROCESAMIENTO DINÁMICO DE CANTIDADES ---
        if conector_listo and st.session_state["modo_cantidades"] == "Modelo Revit 3D":
            revit_df = st.session_state["revit_raw_df"].copy()
            col_desc = st.session_state.get("col_desc_global", revit_df.columns[0])
            col_mat = st.session_state.get("col_mat_global", "NO_USAR")
            
            if col_mat != "NO_USAR" and col_mat in revit_df.columns:
                revit_df["Identificador_Compuesto"] = revit_df[col_desc].astype(str) + " | " + revit_df[col_mat].astype(str)
            else:
                revit_df["Identificador_Compuesto"] = revit_df[col_desc].astype(str)
                
            identificador_col = "Identificador_Compuesto"
            
            for col in revit_df.columns:
                if col not in [col_desc, col_mat, identificador_col]:
                    revit_df[col + "_clean"] = revit_df[col].apply(clean_numeric_value)
            
            cantidades_revit_acumuladas = {row["CodPar"]: 0.0 for _, row in df_pres.iterrows()}
            partidas_mapeadas_set = set()
            
            for _, row in revit_df.iterrows():
                elem_name = row[identificador_col]
                if elem_name in st.session_state["advanced_mapping"]:
                    map_data = st.session_state["advanced_mapping"][elem_name]
                    codigos_lulo = map_data.get("codes", [])
                    fallback_col = revit_df.columns[-1] if len(revit_df.columns) > 1 else revit_df.columns[0]
                    col_usar = map_data.get("col_cant", fallback_col) + "_clean"
                    factor = float(map_data.get("factor", 1.0))
                    
                    if col_usar in revit_df.columns:
                        elem_qty = row[col_usar] * factor
                    else:
                        elem_qty = 0.0
                        
                    for cod in codigos_lulo:
                        if cod != "NINGUNA / EXCLUIR" and cod in cantidades_revit_acumuladas:
                            cantidades_revit_acumuladas[cod] += elem_qty
                            partidas_mapeadas_set.add(cod)
            
            def asignar_cantidad_activa(row):
                cod = row["CodPar"]
                if cod in partidas_mapeadas_set:
                    return cantidades_revit_acumuladas[cod]
                else:
                    return 0.00 if st.session_state["no_modelados_cero"] else row["CanPar"]
            
            df_pres["CanPar_Active"] = df_pres.apply(asignar_cantidad_activa, axis=1)
            st.sidebar.success("⚡ Cómputos BIM Sincronizados.")
        else:
            df_pres["CanPar_Active"] = df_pres["CanPar"]

        df_pres["STotPar_Active"] = df_pres["CanPar_Active"] * df_pres["PreUni"]
        monto_total = float(df_pres["STotPar_Active"].sum())
        costo_directo = float((df_pres["CanPar_Active"] * df_pres["SCosDir"]).sum())
        total_admin = float((df_pres["CanPar_Active"] * df_pres["SAdmini"]).sum())
        total_utilidad = float((df_pres["CanPar_Active"] * df_pres["SUtilid"]).sum())
        
        mat_totales = float((df_pres["CanPar_Active"] * df_pres["UniMat"]).sum())
        equ_totales = float((df_pres["CanPar_Active"] * df_pres["UniEqu"]).sum())
        man_totales = float((df_pres["CanPar_Active"] * df_pres["UniMan"]).sum())

        opcion = st.sidebar.radio("Nivel de Análisis Gerencial:", [
            "1. Resumen Ejecutivo de Costos",
            "2. Análisis por Capítulos de Obra",
            "3. Control de Riesgos (Pareto)",
            "4. Hoja Técnica de APU Detallado",
            "5. Explosión Global de Insumos",
            "6. Conciliador BIM 5D (Revit)"
        ])

        if opcion == "1. Resumen Ejecutivo de Costos":
            st.markdown(f"#### 📐 Análisis del Contrato: *{df_proy.get('Descri', 'Proyecto')}*")
            if st.session_state["modo_cantidades"] == "Modelo Revit 3D":
                st.warning("⚠️ ESTÁS VISUALIZANDO EL PRESUPUESTO BASADO EN EL MODELO BIM 3D DE REVIT")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("MONTO TOTAL CALCULADO", f"${monto_total:,.2f}")
            c2.metric("COSTO DIRECTO BASE (CD)", f"${costo_directo:,.2f}")
            c3.metric("GASTOS DE ADMINISTRACIÓN", f"${total_admin:,.2f}")
            c4.metric("MARGEN DE UTILIDAD PROYECTADO", f"${total_utilidad:,.2f}")
            
            st.write("---")
            col_izq, col_der = st.columns([3, 2])
            with col_izq:
                st.write("##### **Estructura del Costo Directo de Campo**")
                df_comp = pd.DataFrame({"Componente": ["Materiales", "Mano de Obra", "Equipos y Maquinaria"], "Monto ($)": [mat_totales, man_totales, equ_totales]})
                total_cd_calc = mat_totales + man_totales + equ_totales
                df_comp["Porcentaje"] = (df_comp["Monto ($)"] / (total_cd_calc if total_cd_calc > 0 else 1)) * 100
                df_comp["Texto Gráfico"] = df_comp.apply(lambda x: f"${x['Monto ($)']:,.2f} ({x['Porcentaje']:.2f}%)", axis=1)
                fig_comp = px.bar(df_comp, x="Monto ($)", y="Componente", orientation="h", color="Componente", text="Texto Gráfico", color_discrete_sequence=["#1F77B4", "#2CA02C", "#D62728"])
                fig_comp.update_layout(showlegend=False, xaxis_title="Monto en USD ($)", yaxis_title="", font=dict(size=14))
                st.plotly_chart(fig_comp, use_container_width=True)
                
            with col_der:
                st.write("##### **Distribución de Recargos Contratados**")
                df_ind = pd.DataFrame({"Concepto": ["Costo Directo Puro", f"Administración ({df_proy.get('Admini', 0.00):.2f}%)", f"Utilidad Proyectada ({df_proy.get('Utilid', 0.00):.2f}%)"], "Monto ($)": [costo_directo, total_admin, total_utilidad]})
                fig_ind = px.pie(df_ind, values="Monto ($)", names="Concepto", color_discrete_sequence=["#2B5C8F", "#4682B4", "#43A047"], hole=0.4)
                fig_ind.update_traces(textinfo='percent+label')
                st.plotly_chart(fig_ind, use_container_width=True)

        elif opcion == "2. Análisis por Capítulos de Obra":
            st.write("#### 📂 Presupuesto de Obra Distribuido por Fases Constructivas")
            df_cap_limpio = df_cap.dropna(subset=['CodCap', 'DesCap']).copy().reset_index(drop=True)
            lista_capitulos = []
            diccionario_partidas_cap = {}
            for idx, row in df_cap_limpio.iterrows():
                partidas_cap = df_pres[(df_pres["NumPar"] >= row["ParDes"]) & (df_pres["NumPar"] <= row["ParHas"])]
                monto_cap = float(partidas_cap["STotPar_Active"].sum())
                nombre_capitulo = f"{int(row['CodCap'])}.- {row['DesCap']}"
                if monto_cap > 0:
                    lista_capitulos.append({"Capítulo": nombre_capitulo, "Inversión Acumulada ($)": monto_cap})
                    diccionario_partidas_cap[nombre_capitulo] = partidas_cap
            df_res_cap = pd.DataFrame(lista_capitulos)
            if not df_res_cap.empty:
                fig_cap = px.bar(df_res_cap, x="Inversión Acumulada ($)", y="Capítulo", orientation="h", text_auto="$,.2f", color="Inversión Acumulada ($)", color_continuous_scale="Greens")
                fig_cap.update_layout(yaxis={'categoryorder':'total ascending'}, font=dict(size=14), height=500)
                st.plotly_chart(fig_cap, use_container_width=True)
                st.write("---")
                cap_sel = st.selectbox("Seleccione una fase para auditar sus partidas internas:", df_res_cap["Capítulo"])
                if cap_sel:
                    df_detalle = diccionario_partidas_cap[cap_sel][['NumPar', 'CodPar', 'NomPar', 'CanPar_Active', 'PreUni', 'STotPar_Active']]
                    df_detalle.columns = ['N°', 'Código', 'Descripción de la Partida', 'Cantidad Activa', 'P.U. ($)', 'Total Asignado ($)']
                    st.dataframe(df_detalle.style.format({'Cantidad Activa': '{:,.2f}', 'P.U. ($)': '${:,.2f}', 'Total Asignado ($)': '${:,.2f}'}), width="stretch")

        elif opcion == "3. Control de Riesgos (Pareto)":
            st.write("#### 📊 Curva ABC: Identificación del 20% de Partidas que Concentran el 80% del Capital")
            df_pareto = df_pres.sort_values(by="STotPar_Active", ascending=False).head(10)[['CodPar', 'NomPar', 'CanPar_Active', 'PreUni', 'STotPar_Active']].reset_index(drop=True)
            df_pareto.columns = ['Código', 'Descripción Corta de la Partida', 'Cantidad Activa', 'Precio Unitario ($)', 'Monto Acumulado ($)']
            fig_pareto = px.bar(df_pareto, x="Monto Acumulado ($)", y="Código", orientation="h", text="Monto Acumulado ($)", hover_data=['Descripción Corta de la Partida'], color="Monto Acumulado ($)", color_continuous_scale="Reds")
            fig_pareto.update_traces(texttemplate='$%{x:,.2f}', textposition='outside')
            fig_pareto.update_layout(yaxis={'categoryorder':'total ascending'}, font=dict(size=14), height=500)
            st.plotly_chart(fig_pareto, use_container_width=True)
            st.dataframe(df_pareto.style.format({'Cantidad Activa': '{:,.2f}', 'Precio Unitario ($)': '${:,.2f}', 'Monto Acumulado ($)': '${:,.2f}'}), width="stretch")

        elif opcion == "4. Hoja Técnica de APU Detallado":
            st.write("#### ⚙️ Auditoría Avanzada de Análisis de Precios Unitarios")
            partidas_con_apu = df_mat["CodPar"].unique()
            df_select = df_pres[df_pres["CodPar"].isin(partidas_con_apu)][["CodPar", "NomPar", "STotPar_Active"]].copy()
            termino_busqueda = st.text_input("🔍 Filtrar partidas por Código o Descripción:", "")
            if termino_busqueda:
                mask = df_select["CodPar"].str.contains(termino_busqueda, case=False, na=False) | df_select["NomPar"].str.contains(termino_busqueda, case=False, na=False)
                df_select = df_select[mask]
            
            df_select["Porcentaje"] = (df_select["STotPar_Active"] / (monto_total if monto_total > 0 else 1)) * 100
            df_select["Selector"] = df_select["CodPar"].astype(str) + " | [" + df_select["Porcentaje"].map("{:.2f}%".format) + "] | " + df_select["NomPar"].astype(str)
            mapa_codigos = dict(zip(df_select["Selector"], df_select["CodPar"]))
            
            if mapa_codigos:
                partida_etiqueta = st.selectbox("Seleccione la partida a descomponer:", options=list(mapa_codigos.keys()))
                if partida_etiqueta:
                    partida_sel = mapa_codigos[partida_etiqueta]
                    datos_p = df_pres[df_pres["CodPar"] == partida_sel].iloc[0]
                    st.markdown("📋 **Especificación Técnica Completa en Contrato:**")
                    st.info(datos_p['NomPar'])
                    st.write("---")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Cantidad de Obra Activa", f"{datos_p['CanPar_Active']:,.2f} {datos_p.get('UniPar', 'UND')}")
                    c2.metric("Rendimiento Diario", f"{datos_p['RenPar']:,.2f} {datos_p.get('UniPar', 'UND')}/Día")
                    c3.metric("Costo Directo Unitario", f"${datos_p['SCosDir']:,.2f}")
                    c4.metric("Precio Unitario de Venta", f"${datos_p['PreUni']:,.2f}")
                    
                    mats = df_mat[df_mat["CodPar"] == partida_sel][["CodIns", "CanIns", "CosIns", "Desper"]]
                    manos = df_mano[df_mano["CodPar"] == partida_sel][["CodIns", "CanIns", "CosIns"]]
                    equs = df_equ[df_equ["CodPar"] == partida_sel][["CodIns", "CanIns", "CosIns", "Deprec"]]
                    
                    mats_t = pd.merge(mats, df_insumos, on="CodIns", how="left")
                    manos_t = pd.merge(manos, df_insumos, on="CodIns", how="left")
                    equs_t = pd.merge(equs, df_insumos, on="CodIns", how="left")
                    
                    st.markdown("### 📦 A. Componente de Materiales")
                    if not mats_t.empty:
                        mats_t["Costo Unitario ($)"] = mats_t["CanIns"] * mats_t["CosIns"] * (1 + mats_t["Desper"] / 100)
                        mats_t["% del Rubro"] = (mats_t["Costo Unitario ($)"] / datos_p['UniMat'] * 100).fillna(0) if datos_p['UniMat'] > 0 else 0
                        st.dataframe(mats_t[["CodIns", "NomIns", "UniIns", "CanIns", "CosIns", "Desper", "Costo Unitario ($)", "% del Rubro"]].rename(columns={"CodIns": "Código Insumo", "NomIns": "Descripción del Material", "UniIns": "Unidad", "CanIns": "Cantidad (Rend)", "CosIns": "Precio Base Lulo ($)", "Desper": "% Desperdicio"}).style.format({"Cantidad (Rend)": "{:,.4f}", "Precio Base Lulo ($)": "${:,.2f}", "% Desperdicio": "{:.2f}%", "Costo Unitario ($)": "${:,.2f}", "% del Rubro": "{:.2f}%"}), width="stretch")
                    else:
                        st.info("Esta partida no contempla materiales directos.")
                    
                    st.write("---")
                    st.markdown("### 👷 B. Componente de Mano de Obra")
                    if not manos_t.empty:
                        manos_t["Costo por Jornada ($)"] = manos_t["CanIns"] * manos_t["CosIns"]
                        manos_t["% del Rubro"] = (manos_t["Costo por Jornada ($)"] / datos_p['SSubMan'] * 100).fillna(0) if datos_p['SSubMan'] > 0 else 0
                        st.dataframe(manos_t[["CodIns", "NomIns", "CanIns", "CosIns", "Costo por Jornada ($)", "% del Rubro"]].rename(columns={"CodIns": "Código Cargo", "NomIns": "Cargo Personal", "CanIns": "Factor de Personal", "CosIns": "Salario Diario Base ($)", "Costo por Jornada ($)": "Total Diario Insumo ($)"}).style.format({"Factor de Personal": "{:,.2f}", "Salario Diario Base ($)": "${:,.2f}", "Total Diario Insumo ($)": "${:,.2f}", "% del Rubro": "{:.2f}%"}), width="stretch")
                    else:
                        st.info("Esta partida no requiere asignación de mano de obra directa.")
                    
                    st.write("---")
                    st.markdown("### 🚜 C. Componente de Equipos y Maquinarias")
                    if not equs_t.empty:
                        equs_t["Costo Deprec/Día ($)"] = equs_t["CanIns"] * equs_t["CosIns"] * equs_t["Deprec"]
                        equs_t["% del Rubro"] = (equs_t["Costo Deprec/Día ($)"] / datos_p['STotEqu'] * 100).fillna(0) if datos_p['STotEqu'] > 0 else 0
                        st.dataframe(equs_t[["CodIns", "NomIns", "CanIns", "CosIns", "Deprec", "Costo Deprec/Día ($)", "% del Rubro"]].rename(columns={"CodIns": "Código Equipo", "NomIns": "Maquinaria / Herramientas", "CanIns": "Cantidad", "CosIns": "Valor de Reposición ($)", "Deprec": "Factor Depreciación"}).style.format({"Cantidad": "{:,.2f}", "Valor de Reposición ($)": "${:,.2f}", "Factor Depreciación": "{:,.5f}", "Costo Deprec/Día ($)": "${:,.2f}", "% del Rubro": "{:.2f}%"}), width="stretch")
                    else:
                        st.info("Esta partida no requiere maquinaria especializada.")
                    
                    st.write("---")
                    st.markdown("### 📝 D. Balance Económico del Precio Unitario")
                    pre_uni_val = datos_p['PreUni'] if datos_p['PreUni'] > 0 else 1 
                    df_apu_balance = pd.DataFrame({"Concepto de la Estructura de Costos": ["1. Costo de Materiales Puro", "2. Costo de Mano de Obra (Con Prestaciones)", "3. Costo de Equipos y Herramientas", "(=) COSTO DIRECTO DE CAMPO (CD)", f"(+) Gastos de Administración ({df_proy.get('Admini', 0):.2f}% s/CD)", f"(+) Utilidad Proyectada ({df_proy.get('Utilid', 0):.2f}% s/CD)", "(=) PRECIO UNITARIO FINAL"], "Monto Unitario ($)": [datos_p['UniMat'], datos_p['UniMan'], datos_p['UniEqu'], datos_p['SCosDir'], datos_p['SAdmini'], datos_p['SUtilid'], datos_p['PreUni']], "% de Incidencia Total": [(datos_p['UniMat'] / pre_uni_val) * 100, (datos_p['UniMan'] / pre_uni_val) * 100, (datos_p['UniEqu'] / pre_uni_val) * 100, (datos_p['SCosDir'] / pre_uni_val) * 100, (datos_p['SAdmini'] / pre_uni_val) * 100, (datos_p['SUtilid'] / pre_uni_val) * 100, 100.00]})
                    st.dataframe(df_apu_balance.style.format({"Monto Unitario ($)": "${:,.2f}", "% de Incidencia Total": "{:.2f}%"}), width="stretch")

        elif opcion == "5. Explosión Global de Insumos":
            st.write("#### 🌍 Explosión Global de Insumos y Cierre Financiero")
            df_pres_base = df_pres[['CodPar', 'CanPar_Active', 'RenPar', 'SSubMan', 'SPreSoc']].copy()
            df_pres_base["RenPar"] = pd.to_numeric(df_pres_base["RenPar"], errors='coerce').fillna(1).replace(0, 1)
            factor_presoc = 1 + (df_proy.get('PreSoc', 0) / 100)
            
            global_man_base = float((df_pres_base["CanPar_Active"] * (df_pres_base["SSubMan"] / df_pres_base["RenPar"])).sum())
            global_presoc = float((df_pres_base["CanPar_Active"] * (df_pres_base["SPreSoc"] / df_pres_base["RenPar"])).sum())

            st.markdown("### 📋 Construcción del Presupuesto (Diagrama de Cascada)")
            fig_waterfall = go.Figure(go.Waterfall(name="Presupuesto", orientation="v", measure=["relative", "relative", "relative", "relative", "relative", "relative", "total"], x=["Materiales", "Equipos", "M.Obra Base", "Prest. Sociales", "Administración", "Utilidad", "TOTAL CONTRATADO"], textposition="outside", text=[f"${v:,.0f}" for v in [mat_totales, equ_totales, global_man_base, global_presoc, total_admin, total_utilidad, monto_total]], y=[mat_totales, equ_totales, global_man_base, global_presoc, total_admin, total_utilidad, monto_total], connector={"line": {"color": "rgb(63, 63, 63)"}}, decreasing={"marker": {"color": "#FF5722"}}, increasing={"marker": {"color": "#2CA02C"}}, totals={"marker": {"color": "#1F77B4"}}))
            fig_waterfall.update_layout(title="Suma Acumulativa de Factores", yaxis_title="Inversión Acumulada en USD ($)", font=dict(size=14), height=500, showlegend=False)
            st.plotly_chart(fig_waterfall, use_container_width=True)

            monto_total_val = monto_total if monto_total > 0 else 1
            df_cierre = pd.DataFrame({"Estructura de Costos del Proyecto": ["1. Materiales Consolidado", "2. Maquinaria y Equipos Consolidado", "3. Mano de Obra Base Consolidado", f"4. Prestaciones Sociales ({df_proy.get('PreSoc', 0):.2f}%)", "(=) COSTO DIRECTO TOTAL", f"(+) Gastos de Administración ({df_proy.get('Admini', 0):.2f}% s/CD)", f"(+) Utilidad Proyectada ({df_proy.get('Utilid', 0):.2f}% s/CD)", "(=) MONTO TOTAL DEL PRESUPUESTO"], "Monto Consolidado ($)": [mat_totales, equ_totales, global_man_base, global_presoc, costo_directo, total_admin, total_utilidad, monto_total], "% de Incidencia Total": [(mat_totales / monto_total_val) * 100, (equ_totales / monto_total_val) * 100, (global_man_base / monto_total_val) * 100, (global_presoc / monto_total_val) * 100, (costo_directo / monto_total_val) * 100, (total_admin / monto_total_val) * 100, (total_utilidad / monto_total_val) * 100, 100.00]})
            st.dataframe(df_cierre.style.format({"Monto Consolidado ($)": "${:,.2f}", "% de Incidencia Total": "{:.2f}%"}), width="stretch")

        # --- MÓDULO 6: CONCILIADOR BIM 5D (AHORA CON MOTOR MULTIVARIABLE Y FACTORES DE CONVERSIÓN) ---
        elif opcion == "6. Conciliador BIM 5D (Revit)":
            st.write("#### 🔌 Sincronizador Multivariable BIM 5D - Lulo Win & Autodesk Revit")
            st.write("Asocia cada elemento de tu modelo 3D con sus partidas correspondientes. Ahora puedes definir la columna de extracción y aplicar factores de conversión matemáticos (ideal para pasar de m³ a kg de acero).")
            
            with st.expander("🧪 ¿No tienes un CSV de Revit a la mano? Descarga un Modelo de Cómputos de Prueba"):
                test_elements = [{"Elemento_Modelo": "Pared de Bloque Arcilla", "Area": "450.25 m2", "Volumen": "67.5 m3"}, {"Elemento_Modelo": "Concreto de Fundación FC=250", "Area": "150.0 m2", "Volumen": "85.50 m3"}, {"Elemento_Modelo": "Acero de Refuerzo Grado 60", "Area": "0.0 m2", "Volumen": "2.10 m3"}]
                df_test_revit = pd.DataFrame(test_elements)
                st.download_button("📥 Descargar Revit_Multicategoria_Prueba.csv", data=df_test_revit.to_csv(index=False), file_name="Revit_Multicategoria_Prueba.csv", mime="text/csv")
            
            st.write("---")
            col_l, col_r = st.columns([1, 1])
            
            with col_l:
                st.write("##### **1. Cargar Reporte de Revit (Materiales o Cantidades)**")
                archivo_subido = st.file_uploader("Arrastra aquí el CSV exportado de Revit limpios", type=["csv"], key="revit_uploader")
                if archivo_subido is not None:
                    try:
                        st.session_state["revit_raw_df"] = load_csv_robustly(archivo_subido)
                        if st.session_state["revit_raw_df"] is not None and not st.session_state["revit_raw_df"].empty:
                            st.success("🟢 Tabla de Revit cargada y depurada en memoria.")
                        else:
                            st.error("❌ El archivo cargado está vacío o su formato es irreconocible.")
                    except Exception as ex:
                        st.error(f"Error cargando archivo: {ex}")
            
            with col_r:
                st.write("##### **2. Mapeos de Equivalencia Existentes**")
                archivo_mapeo = st.file_uploader("Opcional: Cargar archivo de mapeo existente (.csv)", type=["csv"], key="map_uploader")
                if archivo_mapeo is not None:
                    try:
                        df_map_uploaded = load_csv_robustly(archivo_mapeo)
                        if df_map_uploaded is not None and not df_map_uploaded.empty:
                            if "Elemento_Revit" in df_map_uploaded.columns and "Codigo_Lulo" in df_map_uploaded.columns:
                                temp_map = {}
                                for _, map_row in df_map_uploaded.iterrows():
                                    elem = map_row["Elemento_Revit"]
                                    cod = map_row["Codigo_Lulo"]
                                    # Cargar compatibilidad nueva (col_cant y factor)
                                    col_c = map_row.get("Columna_Cantidad", df_map_uploaded.columns[-1] if len(df_map_uploaded.columns)>1 else "Cantidad")
                                    fac = float(map_row.get("Factor", 1.0))
                                    
                                    if elem not in temp_map:
                                        temp_map[elem] = {"codes": [], "col_cant": col_c, "factor": fac}
                                    if cod not in temp_map[elem]["codes"]:
                                        temp_map[elem]["codes"].append(cod)
                                st.session_state["advanced_mapping"] = temp_map
                                st.success("🟢 Matriz multivariable cargada con éxito.")
                            else:
                               st.error("❌ El archivo de mapeo no contiene las columnas necesarias.")
                    except Exception as ex:
                        st.error(f"Error al cargar mapeo: {ex}")

            if st.session_state["revit_raw_df"] is not None and not st.session_state["revit_raw_df"].empty:
                st.write("---")
                st.markdown("### 🗺️ Tablero de Asociación de Conceptos y Unidades")
                
                revit_raw = st.session_state["revit_raw_df"].copy()
                cols_raw = list(revit_raw.columns)
                
                col_sel1, col_sel2 = st.columns(2)
                st.session_state["col_desc_global"] = col_sel1.selectbox("📌 Selecciona la columna del Nombre (Ej: Tipo, Elemento):", cols_raw, index=0)
                
                # Opción para seleccionar una columna secundaria opcional
                opciones_secundarias = ["NO_USAR"] + cols_raw
                st.session_state["col_mat_global"] = col_sel2.selectbox("📌 Opcional: Selecciona una sub-categoría (Ej: Material):", opciones_secundarias, index=0)
                
                col_desc = st.session_state["col_desc_global"]
                col_mat = st.session_state["col_mat_global"]
                
                # Crear el identificador único compuesto para la visualización y el mapeo
                if col_mat != "NO_USAR" and col_mat in revit_raw.columns:
                    revit_raw["Identificador_Compuesto"] = revit_raw[col_desc].astype(str) + " | " + revit_raw[col_mat].astype(str)
                else:
                    revit_raw["Identificador_Compuesto"] = revit_raw[col_desc].astype(str)
                
                identificador_col = "Identificador_Compuesto"
                
                # Pre-limpiar numéricos temporalmente para mostrar previews limpios
                for c in cols_raw:
                    if c not in [col_desc, col_mat]:
                        revit_raw[c + "_clean"] = revit_raw[c].apply(clean_numeric_value)
                
                lulo_dict_items = [(row['CodPar'], row['NomPar']) for _, row in df_pres.iterrows()]
                lulo_options_map = {f"{row['CodPar']} | {row['NomPar']}": row['CodPar'] for _, row in df_pres.iterrows()}
                lulo_display_list = list(lulo_options_map.keys())

                st.write("##### **🤖 Mapeo Lingüístico Automático (Asignará Columnas y Factores por Defecto 1.0):**")
                if st.button("⚡ Ejecutar Mapeo Automático Inteligente", help="Asocia elementos mediante concordancia de palabras clave"):
                    new_mapping = st.session_state["advanced_mapping"].copy()
                    for elem in revit_raw[identificador_col].unique():
                        if elem not in new_mapping or len(new_mapping[elem].get("codes", [])) == 0:
                            # Buscar usando solo la primera parte del nombre si tiene compuesto
                            search_term = elem.split(" | ")[0] if " | " in elem else elem
                            best_match = encontrar_mejor_coincidencia(search_term, lulo_dict_items)
                            new_mapping[elem] = {
                                "codes": [best_match] if best_match != "NINGUNA / EXCLUIR" else [],
                                "col_cant": cols_raw[-1], # Por defecto toma la última
                                "factor": 1.0
                            }
                    st.session_state["advanced_mapping"] = new_mapping
                    st.success("🤖 Mapeo inicial de inteligencia lingüística finalizado.")
                    st.rerun()

                # =========================================================================
                # 🧹 NUEVO GESTOR RÁPIDO DE LIMPIEZA MASIVA DE MAPEOS
                # =========================================================================
                st.write("---")
                st.write("##### **🧹 Gestor Rápido de Limpieza (Desvincular Mapeos)**")
                with st.expander("Abre aquí para desvincular múltiples partidas rápidamente o borrar todo"):
                    if len(st.session_state["advanced_mapping"]) > 0:
                        st.write("Si el mapeo automático asoció cosas incorrectas, bórralas aquí sin buscarlas una por una:")
                        c_borrar1, c_borrar2 = st.columns([3, 1])
                        
                        elementos_mapeados = list(st.session_state["advanced_mapping"].keys())
                        a_borrar = c_borrar1.multiselect("Selecciona los elementos de Revit que deseas DESVINCULAR:", options=elementos_mapeados)
                        
                        if c_borrar1.button("🗑️ Desvincular los elementos seleccionados"):
                            for el in a_borrar:
                                if el in st.session_state["advanced_mapping"]:
                                    del st.session_state["advanced_mapping"][el]
                            st.success("¡Elementos desvinculados exitosamente!")
                            st.rerun()
                            
                        st.write("---")
                        if st.button("🚨 ELIMINAR TODOS LOS MAPEOS (Empezar desde cero)"):
                            st.session_state["advanced_mapping"] = {}
                            st.success("Memoria de mapeos borrada por completo.")
                            st.rerun()
                    else:
                        st.info("No hay mapeos activos actualmente.")

                st.write("---")
                
                # --- PANEL INTERACTIVO MULTIVARIABLE ---
                st.write("### 📝 Panel de Configuración Multivariable:")
                revit_elements = list(revit_raw[identificador_col].dropna().unique())
                
                selected_revit_elem = st.selectbox("👉 Seleccione un Elemento del Modelo de Revit a configurar:", options=revit_elements)
                
                if selected_revit_elem:
                    # Obtener datos guardados de este elemento si existen
                    elem_data = st.session_state["advanced_mapping"].get(selected_revit_elem, {
                        "codes": [], "col_cant": cols_raw[-1] if len(cols_raw)>1 else cols_raw[0], "factor": 1.0
                    })
                    
                    st.markdown(f"#### Parámetros Matemáticos para: **{selected_revit_elem}**")
                    col1, col2 = st.columns(2)
                    
                    # Selector de Columna de Cantidad individual
                    idx_col = cols_raw.index(elem_data["col_cant"]) if elem_data["col_cant"] in cols_raw else len(cols_raw)-1
                    col_cant_especifica = col1.selectbox("📏 ¿De qué columna extraemos el valor?", cols_raw, index=idx_col)
                    
                    # Factor de Conversión
                    factor = col2.number_input("✖️ Factor de Conversión (Ej: 7850 para Acero, 1.0 normal):", value=float(elem_data["factor"]), format="%.4f")
                    
                    # Mostrar Preview Matemático
                    elem_df = revit_raw[revit_raw[identificador_col] == selected_revit_elem]
                    if col_cant_especifica + "_clean" in elem_df.columns:
                        qty_base = elem_df[col_cant_especifica + "_clean"].sum()
                        qty_final = qty_base * factor
                        st.info(f"🔢 **Cálculo en vivo:** `{qty_base:,.4f}` (Lectura de Revit) × `{factor}` (Factor) = **`{qty_final:,.2f}` unidades** que se inyectarán.")
                    else:
                        st.warning("La columna seleccionada no contiene valores numéricos válidos.")

                    # Selector de Partidas de Lulo
                    busqueda_lulo = st.text_input("🔍 Buscador: Escribe palabras de la partida de Lulo (ej: 'acero', 'concreto'):", "")
                    opciones_filtradas = [opt for opt in lulo_display_list if busqueda_lulo.lower() in opt.lower()] if busqueda_lulo else lulo_display_list
                    
                    current_mapped_displays = []
                    for cod in elem_data.get("codes", []):
                        match_p = df_pres[df_pres["CodPar"] == cod]
                        if not match_p.empty:
                            current_mapped_displays.append(f"{cod} | {match_p.iloc[0]['NomPar']}")
                            
                    options_for_multiselect = list(set(opciones_filtradas + current_mapped_displays))
                    asociaciones_seleccionadas = st.multiselect("🔗 Seleccione las partidas de Lulo a las que se les aplicará este cálculo:", options=options_for_multiselect, default=current_mapped_displays)
                    
                    # BOTONES DE GUARDADO Y DESVINCULACIÓN INDIVIDUAL RÁPIDA
                    col_btn1, col_btn2 = st.columns(2)
                    
                    if col_btn1.button("💾 Guardar y Aplicar Mapeo a este Elemento"):
                        nuevos_codigos = [lulo_options_map[opt] for opt in asociaciones_seleccionadas if opt in lulo_options_map]
                        st.session_state["advanced_mapping"][selected_revit_elem] = {
                            "codes": nuevos_codigos,
                            "col_cant": col_cant_especifica,
                            "factor": factor
                        }
                        st.success("🎉 ¡Mapeo y Matemáticas guardadas de forma segura!")
                        st.rerun()
                        
                    if col_btn2.button("🗑️ Desvincular y Limpiar este Elemento"):
                        if selected_revit_elem in st.session_state["advanced_mapping"]:
                            del st.session_state["advanced_mapping"][selected_revit_elem]
                            st.success("Mapeo eliminado para este elemento.")
                            st.rerun()

                st.write("---")
                
                # --- EXPORTAR ARCHIVO DE MAPEO ---
                if len(st.session_state["advanced_mapping"]) > 0:
                    st.write("##### 💾 ¿Terminaste el mapeo? Guárdalo para el futuro:")
                    export_rows = []
                    for elem, data in st.session_state["advanced_mapping"].items():
                        for cod in data.get("codes", []):
                            if cod != "NINGUNA / EXCLUIR":
                                export_rows.append({
                                    "Elemento_Revit": elem, 
                                    "Codigo_Lulo": cod,
                                    "Columna_Cantidad": data["col_cant"],
                                    "Factor": data["factor"]
                                })
                    df_export_map = pd.DataFrame(export_rows)
                    if not df_export_map.empty:
                        csv_mapped = df_export_map.to_csv(index=False)
                        st.download_button("📥 Exportar Matriz de Mapeo Multivariable (.csv)", data=csv_mapped, file_name="Matriz_Mapeo_BIM5D_Avanzada.csv", mime="text/csv")

                # --- TABLA DE AUDITORÍA CON MAPPING AVANZADO ---
                if conector_listo and st.session_state["modo_cantidades"] == "Modelo Revit 3D":
                    st.write("---")
                    st.write("#### 🔍 Auditoría de Desviaciones de Ingeniería (Lulo vs Revit Mapeado)")
                    
                    expanded_rows = []
                    for _, r_row in revit_raw.iterrows():
                        elem_name = r_row[identificador_col]
                        if elem_name in st.session_state["advanced_mapping"]:
                            data = st.session_state["advanced_mapping"][elem_name]
                            col_c = data["col_cant"] + "_clean"
                            fac = float(data["factor"])
                            if col_c in r_row.index:
                                qty = r_row[col_c] * fac
                                for c in data.get("codes", []):
                                    # Pasamos el nombre del elemento compuesto para auditar qué se sumó
                                    expanded_rows.append({"CodPar": c, "Cantidad_Revit_Item": qty, "Elemento_Revit_Origen": elem_name})
                    
                    if expanded_rows:
                        df_expanded_revit = pd.DataFrame(expanded_rows)
                        # Agrupación N-a-1: Suma las cantidades y concatena los nombres para el rastro de auditoría
                        cantidades_mapeadas = df_expanded_revit.groupby("CodPar").agg({
                            "Cantidad_Revit_Item": "sum",
                            "Elemento_Revit_Origen": lambda x: " + ".join(pd.unique(x))
                        }).reset_index()
                        cantidades_mapeadas.columns = ["CodPar", "Cantidad_Revit", "Elementos_Revit_Agrupados"]
                    else:
                        cantidades_mapeadas = pd.DataFrame(columns=["CodPar", "Cantidad_Revit", "Elementos_Revit_Agrupados"])
                    
                    df_audit = pd.merge(df_pres, cantidades_mapeadas, on="CodPar", how="outer")
                    df_audit["CanPar"] = df_audit["CanPar"].fillna(0.00)
                    df_audit["Cantidad_Revit"] = df_audit["Cantidad_Revit"].fillna(0.00)
                    df_audit["PreUni"] = df_audit["PreUni"].fillna(0.00)
                    df_audit["NomPar"] = df_audit["NomPar"].fillna("No mapeado en Lulo Win")
                    df_audit["CodPar"] = df_audit["CodPar"].fillna("S/C")
                    
                    # Proteger la columna de elementos agrupados en caso de que esté vacía
                    if "Elementos_Revit_Agrupados" in df_audit.columns:
                        df_audit["Elementos_Revit_Agrupados"] = df_audit["Elementos_Revit_Agrupados"].fillna("-")
                    else:
                        df_audit["Elementos_Revit_Agrupados"] = "-"
                    
                    df_audit["Diferencia_Cantidad"] = df_audit["Cantidad_Revit"] - df_audit["CanPar"]
                    df_audit["Diferencia_Porcentual (%)"] = df_audit.apply(lambda x: (x["Diferencia_Cantidad"] / x["CanPar"] * 100) if x["CanPar"] > 0 else (100.00 if x["Cantidad_Revit"] > 0 else 0.00), axis=1)
                    df_audit["Impacto_Financiero ($)"] = df_audit["Diferencia_Cantidad"] * df_audit["PreUni"]
                    
                    def clasificiar_estado(row):
                        if row["CanPar"] == 0 and row["Cantidad_Revit"] > 0:
                            return "🔴 Omisión en Presupuesto (No cobrado)"
                        elif row["Cantidad_Revit"] == 0 and row["CanPar"] > 0:
                            return "🔵 Omisión en Modelo 3D (No modelado)"
                        elif abs(row["Diferencia_Porcentual (%)"]) < 0.1:
                            return "🟢 Match Perfecto"
                        else:
                            return "🟡 Discrepancia Física"
                    df_audit["Estado Conciliación"] = df_audit.apply(clasificiar_estado, axis=1)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Match Perfecto", f"{len(df_audit[df_audit['Estado Conciliación'].str.startswith('🟢')])} partidas")
                    c2.metric("Discrepancias Cómputos", f"{len(df_audit[df_audit['Estado Conciliación'].str.startswith('🟡')])} partidas", delta="-", delta_color="inverse")
                    c3.metric("Faltan en Presupuesto", f"{len(df_audit[df_audit['Estado Conciliación'].str.startswith('🔴')])} partidas", delta_color="off")
                    c4.metric("Faltan en Revit", f"{len(df_audit[df_audit['Estado Conciliación'].str.startswith('🔵')])} partidas", delta_color="off")
                    
                    estado_filtro = st.multiselect("Filtrar Auditoría por Estado:", ["🟢 Match Perfecto", "🟡 Discrepancia Física", "🔴 Omisión en Presupuesto (No cobrado)", "🔵 Omisión en Modelo 3D (No modelado)"], default=["🟡 Discrepancia Física", "🔴 Omisión en Presupuesto (No cobrado)", "🔵 Omisión en Modelo 3D (No modelado)"])
                    df_audit_visual = df_audit[df_audit["Estado Conciliación"].isin(estado_filtro)].copy()
                    df_audit_visual = df_audit_visual[["CodPar", "NomPar", "Elementos_Revit_Agrupados", "CanPar", "Cantidad_Revit", "Diferencia_Cantidad", "Diferencia_Porcentual (%)", "PreUni", "Impacto_Financiero ($)", "Estado Conciliación"]].sort_values(by="Impacto_Financiero ($)", key=abs, ascending=False).reset_index(drop=True)
                    
                    # Mostrar tabla de auditoría con la nueva mejora
                    df_audit_visual.columns = ["Código", "Descripción Lulo", "🧩 Elementos Sumados de Revit", "Cant. Lulo", "Cant. Revit", "Dif. Cantidad", "Desv. (%)", "P.U. ($)", "Impacto ($)", "Auditoría de Conciliación"]
                    st.dataframe(df_audit_visual.style.format({"Cant. Lulo": "{:,.2f}", "Cant. Revit": "{:,.2f}", "Dif. Cantidad": "{:,.2f}", "Desv. (%)": "{:.2f}%", "P.U. ($)": "${:,.2f}", "Impacto ($)": "${:,.2f}"}), width="stretch", height=500)

    except Exception as e:
        st.error(f"⚠️ Error al sincronizar los datos relacionales avanzados del proyecto. Por favor verifica tus archivos CSV.")
        st.code(str(e))