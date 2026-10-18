import streamlit as st
import pandas as pd
import io
import requests
from datetime import datetime

st.set_page_config(page_title="Gestor de Dotaciones PRO", layout="wide")

st.title("📦 Gestor Visual de Dotaciones PRO")
st.write("Generación automatizada con separación por cuentas, códigos de picking y BBDD en la nube.")

# Variables de estado (Session State) para almacenar el carrito
if 'dotaciones' not in st.session_state:
    st.session_state.dotaciones = []

# --- 1. CONFIGURACIÓN GENERAL (Barra lateral) ---
st.sidebar.header("⚙️ Datos del Envío")
fecha_pedido = st.sidebar.date_input("Fecha del pedido")
fecha_salida = st.sidebar.date_input("Fecha deseada de salida")
campana = st.sidebar.text_input("Campaña")
transporte = st.sidebar.selectbox("Tipo de Transporte", ["TIPSA", "RECOGEN"])

# --- 2. CARGA DE ARCHIVOS DESDE LA NUBE ---
st.subheader("1. Bases de Datos (En vivo)")

# Usamos export=csv para la BBDD porque es mucho más robusto en Google Drive
URL_EXPORT = "https://docs.google.com/spreadsheets/d/1sglb7tI0L0TfzIz-ICY84eu5SkRL_SPz/export?format=xlsx"
URL_USUARIOS = "https://docs.google.com/spreadsheets/d/11WxnNJa-1NNjwRqMrHb2uH2bShoCd8JrPwD-WJRcyeM/export?format=csv"

# Función robusta para leer desde Google Drive
@st.cache_data(ttl=60)
def cargar_excel_desde_nube(url, es_csv=False):
    respuesta = requests.get(url)
    respuesta.raise_for_status()
    if es_csv:
        return pd.read_csv(io.StringIO(respuesta.content.decode('utf-8')))
    else:
        return pd.read_excel(io.BytesIO(respuesta.content))

try:
    with st.spinner('Cargando catálogo del almacén...'):
        df_export = cargar_excel_desde_nube(URL_EXPORT, es_csv=False).dropna(subset=['Código de artículo'])
    st.success("📦 Catálogo del almacén cargado.")

    with st.spinner('Cargando BBDD de usuarios...'):
        df_users = cargar_excel_desde_nube(URL_USUARIOS, es_csv=True)
    st.success("👥 BBDD de consignatarios cargada.")
    st.info("💡 Si modificas la BBDD en Google Drive, pulsa F5 aquí para actualizar los datos.")
    
    carga_exitosa = True
except Exception as e:
    st.error("⚠️ Error al conectar con la nube.")
    st.write(f"Detalle técnico del error: {e}")
    carga_exitosa = False

# --- 3. ASIGNACIÓN A USUARIO ---
if carga_exitosa:
    st.markdown("---")
    st.subheader("2. Asignación")
    
    lista_nombres = df_users['Nombre'].dropna().tolist()
    usuario_seleccionado = st.selectbox("Selecciona el Consignatario", ["-- Seleccionar --"] + lista_nombres)

    if usuario_seleccionado != "-- Seleccionar --":
        st.markdown("---")
        st.subheader(f"🛒 Productos para: {usuario_seleccionado}")
        
        user_data = df_users[df_users['Nombre'] == usuario_seleccionado].iloc[0]

        with st.form("form_productos"):
            st.write("Indica la cantidad (deja en 0 lo que no quieras).")
            cantidades = {}
            
            for index, row in df_export.iterrows():
                codigo = str(row['Código de artículo']).strip()
                desc = str(row['Descripción (1)']).strip()
                departamento = str(row.get('Código de departamento', '')).strip().upper()
                
                # Mapear cuenta
                if "METAGPV" in departamento:
                    cuenta_id = "212"
                elif "METAPROMO" in departamento:
                    cuenta_id = "216"
                else:
                    cuenta_id = departamento

                c1, c2 = st.columns([5, 2])
                c1.write(f"**{codigo}** - {desc} *(Cuenta: {cuenta_id})*")
                cantidades[index] = c2.number_input(f"Uds {codigo}", min_value=0, value=0, key=f"qty_{index}", label_visibility="collapsed")
            
            if st.form_submit_button("Añadir al Listado"):
                agregados = 0
                for idx, qty in cantidades.items():
                    if qty > 0:
                        row = df_export.loc[idx]
                        departamento = str(row.get('Código de departamento', '')).strip().upper()
                        if "METAGPV" in departamento:
                            cuenta_id = "212"
                        elif "METAPROMO" in departamento:
                            cuenta_id = "216"
                        else:
                            cuenta_id = departamento
                        
                        st.session_state.dotaciones.append({
                            'CUENTA': cuenta_id,
                            'CONSIGNATARIO': user_data['Nombre'],
                            'DIRECCION': user_data.get('Direccion', ''),
                            'CP': user_data.get('CP', ''),
                            'PROVINCIA': user_data.get('Provincia', ''),
                            'POBLACION': user_data.get('Poblacion', ''),
                            'PAIS': user_data.get('Pais', ''),
                            'TELEFONO': user_data.get('Telefono', ''),
                            'CONTACTO': user_data.get('Contacto', ''),
                            'EMAIL': user_data.get('Email', ''),
                            'REFERENCIA': row['Código de artículo'],
                            'DESCRIPCION': row['Descripción (1)'],
                            'CANTIDAD': qty
                        })
                        agregados += 1
                if agregados > 0:
                    st.success(f"✅ Añadidos {agregados} productos a {usuario_seleccionado}.")
                    st.rerun()

# --- 4. GENERACIÓN DE EXCELS ---
if st.session_state.dotaciones:
    st.markdown("---")
    st.subheader("📋 Resumen de Dotaciones")
    
    df_carrito = pd.DataFrame(st.session_state.dotaciones)
    st.dataframe(df_carrito[['CUENTA', 'CONSIGNATARIO', 'REFERENCIA', 'DESCRIPCION', 'CANTIDAD']])
    
    if st.button("🗑️ Limpiar carrito"):
        st.session_state.dotaciones = []
        st.rerun()

    st.markdown("### 📥 Descargar Plantillas")
    
    # Asignar Códigos de Picking
    usuarios_unicos = df_carrito['CONSIGNATARIO'].unique()
    mapa_picking = {usuario: f"PICK-{i+1:03d}" for i, usuario in enumerate(usuarios_unicos)}

    cuentas_presentes = df_carrito['CUENTA'].unique()
    
    for cuenta in cuentas_presentes:
        df_cuenta = df_carrito[df_carrito['CUENTA'] == cuenta].copy()
        
        columnas_dot = ['FECHA', 'CUENTA', 'CAMPAÑA', 'FECHA DESEADA DE SALIDA', 'CONSIGNATARIO', 
                        'DIRECCION DEL CONSIGNATARIO', 'CP', 'PROVINCIA', 'POBLACION', 'CODIGO PICKING', 
                        'REFERENCIA', 'CANTIDAD', 'NOTAS', 'TIPO DE TRANSPORTE', 'TIPO ERROR', 
                        'PAIS', 'CODIGO EMPRESA', 'TELEFONO', 'PERSONA CONTACTO', 'EMAIL CONTACTO']
        
        df_final = pd.DataFrame(columns=columnas_dot)
        
        for i, row in df_cuenta.iterrows():
            df_final.loc[i] = {
                'FECHA': fecha_pedido.strftime("%d/%m/%Y"),
                'CUENTA': row['CUENTA'],
                'CAMPAÑA': campana,
                'FECHA DESEADA DE SALIDA': fecha_salida.strftime("%d/%m/%Y"),
                'CONSIGNATARIO': row['CONSIGNATARIO'],
                'DIRECCION DEL CONSIGNATARIO': row['DIRECCION'],
                'CP': row['CP'],
                'PROVINCIA': row['PROVINCIA'],
                'POBLACION': row['POBLACION'],
                'CODIGO PICKING': mapa_picking[row['CONSIGNATARIO']],
                'REFERENCIA': row['REFERENCIA'],
                'CANTIDAD': row['CANTIDAD'],
                'NOTAS': row['DESCRIPCION'],
                'TIPO DE TRANSPORTE': transporte,
                'TIPO ERROR': '',
                'PAIS': row['PAIS'],
                'CODIGO EMPRESA': '',
                'TELEFONO': row['TELEFONO'],
                'PERSONA CONTACTO': row['CONTACTO'],
                'EMAIL CONTACTO': row['EMAIL']
            }
        
        df_final = df_final.fillna("")
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_final.to_excel(writer, sheet_name='DOT', index=False, startrow=1)
        
        st.download_button(
            label=f"⬇️ Descargar Excel (Cuenta: {cuenta})",
            data=buffer.getvalue(),
            file_name=f"Dotaciones_{cuenta}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_{cuenta}"
        )