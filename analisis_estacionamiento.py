import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader
import os
import base64
from datetime import datetime

# Función para convertir imagen a base64
def imagen_base64(ruta):
    with open(ruta, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

# Función para generar HTML desde plantilla
def generar_html(grafico_carros_b64, grafico_tarifas_b64, grafico_histograma_b64,
                 resumen_kpi, tabla_inusuales_html, archivo_origen, fecha_generacion, logo_src,
                 plantilla="reporte_template.html"):
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template(plantilla)
    return template.render(
        grafico_carros=f"data:image/png;base64,{grafico_carros_b64}",
        grafico_tarifas=f"data:image/png;base64,{grafico_tarifas_b64}",
        grafico_histograma=f"data:image/png;base64,{grafico_histograma_b64}",
        tabla_kpi=resumen_kpi.to_html(index=False),
        tabla_inusuales=tabla_inusuales_html,
        archivo_origen=archivo_origen,
        fecha_generacion=fecha_generacion,
        logo_src=logo_src
    )

# Cargar logo
logo_b64 = imagen_base64("icono.ico")
logo_src = f"data:image/x-icon;base64,{logo_b64}"
fecha_generacion = datetime.now().strftime("%d/%m/%Y")

# Subir múltiples archivos
archivos = st.file_uploader("Sube uno o más archivos Excel", type=["xlsx"], accept_multiple_files=True)

if archivos:
    dfs = []
    for archivo in archivos:
        df_temp = pd.read_excel(archivo)
        df_temp['__archivo__'] = archivo.name
        dfs.append(df_temp)

    df = pd.concat(dfs, ignore_index=True)

    archivos_disponibles = df['__archivo__'].unique()
    archivo_seleccionado = st.selectbox("📂 Filtra por archivo", archivos_disponibles)
    df = df[df['__archivo__'] == archivo_seleccionado]

    df['CheckIn_Date'] = pd.to_datetime(df['CheckIn_Date'], errors='coerce')
    df['CheckOut_Date'] = pd.to_datetime(df.get('CheckOut_Date'), errors='coerce')

    fechas_invalidas = df['CheckIn_Date'].isna().sum()
    if fechas_invalidas > 0:
        st.caption(f"⚠️ Se ignoraron {fechas_invalidas} registros con fechas inválidas.")

    df_validas = df[df['CheckIn_Date'].notna()].copy()
    df_validas['Mes'] = df_validas['CheckIn_Date'].dt.to_period('M').astype(str)

    meses_disponibles = sorted(df_validas['Mes'].unique())
    mes_seleccionado = st.selectbox("📅 Filtra por mes", meses_disponibles)
    df_filtrado = df_validas[df_validas['Mes'] == mes_seleccionado]

    carros_por_mes = df_validas['Mes'].value_counts().sort_index()
    st.subheader("🚗 Cantidad de carros por mes")
    st.bar_chart(carros_por_mes)

    df['Parking_Cost'] = pd.to_numeric(df['Parking_Cost'], errors='coerce')
    pago_promedio = df['Parking_Cost'].mean()
    st.subheader("💰 Pago promedio")
    st.metric("Promedio", f"${pago_promedio:.2f}")

    st.subheader("📈 Distribución de tarifas")
    conteo_tarifas = df['Parking_Cost'].value_counts().sort_index()
    porcentaje_tarifas = df['Parking_Cost'].value_counts(normalize=True).sort_index() * 100
    tabla_tarifas = pd.DataFrame({
        "Tarifa": conteo_tarifas.index,
        "Cantidad": conteo_tarifas.values,
        "Porcentaje (%)": porcentaje_tarifas.values
    })
    st.dataframe(tabla_tarifas)
    st.bar_chart(tabla_tarifas.set_index("Tarifa")["Cantidad"])

    st.subheader("📊 Histograma de tarifas")
    tarifas_numericas = pd.to_numeric(df['Parking_Cost'], errors='coerce').dropna()
    hist_data = np.histogram(tarifas_numericas, bins=20)
    hist_df = pd.DataFrame({
        "Rango": [f"{round(b,2)}–{round(hist_data[1][i+1],2)}" for i, b in enumerate(hist_data[1][:-1])],
        "Cantidad": hist_data[0]
    })
    st.bar_chart(hist_df.set_index("Rango"))

    if 'CheckOut_Date' in df.columns:
        df['Duración (hrs)'] = (df['CheckOut_Date'] - df['CheckIn_Date']).dt.total_seconds() / 3600
        duracion_promedio = df['Duración (hrs)'].mean()
        st.subheader("⏱️ Duración promedio")
        st.metric("Promedio", f"{duracion_promedio:.2f} horas")

    st.download_button(
        label="📥 Descargar datos filtrados",
        data=df_filtrado.to_csv(index=False).encode('utf-8'),
        file_name="datos_filtrados.csv",
        mime="text/csv"
    )

    st.subheader("📋 KPIs por mes")
    agrupamiento = {
        'Parking_Cost': 'mean',
        'CheckIn_Date': 'count'
    }
    if 'Duración (hrs)' in df_validas.columns:
        agrupamiento['Duración (hrs)'] = 'mean'
    resumen_kpi = df_validas.groupby('Mes').agg(agrupamiento).reset_index()
    resumen_kpi = resumen_kpi.rename(columns={
        'Parking_Cost': 'Pago promedio',
        'CheckIn_Date': 'Cantidad de carros',
        'Duración (hrs)': 'Duración promedio'
    })
    st.dataframe(resumen_kpi)

    st.subheader("🚨 Tarifas inusuales")
    umbral = df['Parking_Cost'].quantile(0.95)
    tarifas_altas = df[df['Parking_Cost'] > umbral]
    st.write(f"Se detectaron {len(tarifas_altas)} registros con tarifas superiores al percentil 95 (${umbral:.2f})")
    st.dataframe(tarifas_altas[['CheckIn_Date', 'Parking_Cost']])
    tabla_inusuales_html = tarifas_altas[['CheckIn_Date', 'Parking_Cost']].to_html(index=False)

    # Guardar gráficos como imágenes
    fig1, ax1 = plt.subplots()
    carros_por_mes.plot(kind='bar', ax=ax1)
    fig1.savefig("grafico_carros.png", bbox_inches='tight', dpi=300)

    fig2, ax2 = plt.subplots()
    tabla_tarifas.set_index("Tarifa")["Cantidad"].plot(kind='bar', ax=ax2)
    fig2.savefig("grafico_tarifas.png", bbox_inches='tight', dpi=300)

    fig3, ax3 = plt.subplots()
    hist_df.set_index("Rango")["Cantidad"].plot(kind='bar', ax=ax3)
    fig3.savefig("grafico_histograma.png", bbox_inches='tight', dpi=300)

    # Convertir imágenes a base64
    grafico_carros_b64 = imagen_base64("grafico_carros.png")
    grafico_tarifas_b64 = imagen_base64("grafico_tarifas.png")
    grafico_histograma_b64 = imagen_base64("grafico_histograma.png")

    # Generar HTML
    html = generar_html(
        grafico_carros_b64,
        grafico_tarifas_b64,
        grafico_histograma_b64,
        resumen_kpi,
        tabla_inusuales_html,
        archivo_seleccionado,
        fecha_generacion,
        logo_src
    )

    with open("reporte_estacionamiento.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("reporte_estacionamiento.html", "rb") as f:
        st.download_button(
            label="📥 Descargar reporte HTML",
            data=f.read(),
            file_name="reporte_estacionamiento.html",
            mime="text/html"
        )
    st.info("Puedes abrir el archivo HTML en tu navegador y usar **Imprimir → Guardar como PDF** para obtener una versión en PDF.")