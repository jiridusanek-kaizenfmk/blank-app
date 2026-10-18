import streamlit as st
import pandas as pd
import io
from datetime import datetime

st.set_page_config(page_title="Gestor de Dotaciones PRO", layout="wide")

st.title("📦 Gestor Visual de Dotaciones PRO")
st.write("Generación automatizada con separación por cuentas y códigos de picking.")

# Variables de estado
if 'dotaciones' not in st.session_state:
    st.session_state.dotaciones = []

# --- 1. CONFIGURACIÓN GENERAL ---
st.sidebar.header("⚙️ Datos del Envío")
fecha_pedido = st.sidebar.date_input("Fecha del pedido")
fecha_salida = st.sidebar.date_input("Fecha deseada de salida")
campana = st.sidebar.text_input("Campaña")
transporte = st.sidebar.selectbox("Tipo de Transporte", ["TIPSA", "RECOGEN"])

# --- 2. CARGA DE ARCHIVOS ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("1. Carga de Archivos")
    file_usuarios = st.file_uploader("Sube tu BBDD de Usuarios (usuarios.xlsx)", type=['xlsx'])
    file_export = st.file_uploader("Sube el Export del Almacén", type=['xlsx'])

if file_usuarios is not None and file_export is not None:
    df_users = pd.read_excel(file_usuarios)
    df_export = pd.read_excel(file_export).dropna(subset=['Código de artículo'])
    
    with col2:
        st.subheader("2. Asignación a Usuario")
        usuario_seleccionado = st.selectbox("Selecciona el Consignatario", ["-- Seleccionar --"] + df_users['Nombre'].tolist())

    if usuario_seleccionado != "-- Seleccionar --":
        st.markdown("---")
        st.subheader(f"🛒 Productos para: {usuario_seleccionado}")
        user_data = df_users[df_users['Nombre'] == usuario_seleccionado].iloc[0]

        with st.form("form_productos"):
            cantidades = {}
            for index, row in df_export.iterrows():
                codigo = str(row['Código de artículo']).strip()
                desc = str(row['Descripción (1)']).strip()
                departamento = str(row['Código de departamento']).strip().upper()
                
                # Mapear la cuenta automáticamente según el departamento
                cuenta_id = "212" if "METAGPV" in departamento else ("216" if "METAPROMO" in departamento else departamento)

                c1, c2 = st.columns([5, 2])
                c1.write(f"**{codigo}** - {desc} *(Cuenta: {cuenta_id})*")
                cantidades[index] = c2.number_input(f"Uds {codigo}", min_value=0, value=0, key=f"qty_{index}", label_visibility="collapsed")
            
            if st.form_submit_button("Añadir al Listado"):
                agregados = 0
                for idx, qty in cantidades.items():
                    if qty > 0:
                        row = df_export.loc[idx]
                        departamento = str(row['Código de departamento']).strip().upper()
                        cuenta_id = "212" if "METAGPV" in departamento else ("216" if "METAPROMO" in departamento else departamento)
                        
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
                    st.success(f"✅ Añadidos {agregados} productos. ¡Puedes seguir añadiendo a otros usuarios!")
                    st.rerun()

# --- 3. GENERACIÓN DE EXCELS ---
if st.session_state.dotaciones:
    st.markdown("---")
    st.subheader("📋 Resumen de Dotaciones")
    
    df_carrito = pd.DataFrame(st.session_state.dotaciones)
    st.dataframe(df_carrito[['CUENTA', 'CONSIGNATARIO', 'REFERENCIA', 'DESCRIPCION', 'CANTIDAD']])
    
    if st.button("🗑️ Limpiar todo"):
        st.session_state.dotaciones = []
        st.rerun()

    st.markdown("### 📥 Descargar Plantillas")
    st.write("Si hay productos de múltiples cuentas, se generarán archivos separados.")
    
    # Asignar Códigos de Picking únicos por Consignatario
    usuarios_unicos = df_carrito['CONSIGNATARIO'].unique()
    mapa_picking = {usuario: f"PICK-{i+1:03d}" for i, usuario in enumerate(usuarios_unicos)}

    # Separar por cuentas y generar Excels
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
                'NOTAS': row['DESCRIPCION'], # El nombre del producto en las notas
                'TIPO DE TRANSPORTE': transporte,
                'TIPO ERROR': '',
                'PAIS': row['PAIS'],
                'CODIGO EMPRESA': '',
                'TELEFONO': row['TELEFONO'],
                'PERSONA CONTACTO': row['CONTACTO'],
                'EMAIL CONTACTO': row['EMAIL']
            }
        
        # Buffer de memoria para el Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Plantilla: empieza en la fila 1 (index 0) para encabezados, como en una tabla limpia.
            # Puedes ajustar startrow=1 si tu plantilla exige la fila 1 vacía.
            df_final.to_excel(writer, sheet_name='DOT', index=False, startrow=1)
        
        # Botón de descarga dinámico por cada cuenta
        st.download_button(
            label=f"⬇️ Descargar Excel para Cuenta {cuenta}",
            data=buffer.getvalue(),
            file_name=f"Plantilla_Dotaciones_Cuenta_{cuenta}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_{cuenta}"
        )