import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader
import os
import base64

# Función para convertir imagen a base64
def imagen_base64(ruta):
    with open(ruta, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

# Función para generar HTML desde plantilla
def generar_html(grafico_carros_b64, grafico_tarifas_b64, resumen_kpi, plantilla="reporte_template.html"):
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template(plantilla)
    return template.render(
        grafico_carros=f"data:image/png;base64,{grafico_carros_b64}",
        grafico_tarifas=f"data:image/png;base64,{grafico_tarifas_b64}",
        tabla_kpi=resumen_kpi.to_html(index=False)
    )

# Subir archivo
archivo = st.file_uploader("Sube el archivo Excel", type=["xlsx"])

if archivo:
    df = pd.read_excel(archivo)

    # Convertir fechas
    df['CheckIn_Date'] = pd.to_datetime(df['CheckIn_Date'], errors='coerce')
    df['CheckOut_Date'] = pd.to_datetime(df.get('CheckOut_Date'), errors='coerce')

    # Mostrar advertencia si hay fechas inválidas
    fechas_invalidas = df['CheckIn_Date'].isna().sum()
    if fechas_invalidas > 0:
        st.caption(f"⚠️ Se ignoraron {fechas_invalidas} registros con fechas inválidas.")

    # Filtrar fechas válidas
    df_validas = df[df['CheckIn_Date'].notna()].copy()
    df_validas['Mes'] = df_validas['CheckIn_Date'].dt.to_period('M').astype(str)

    # Filtro interactivo por mes
    meses_disponibles = sorted(df_validas['Mes'].unique())
    mes_seleccionado = st.selectbox("📅 Filtra por mes", meses_disponibles)
    df_filtrado = df_validas[df_validas['Mes'] == mes_seleccionado]

    # 🚗 Carros por mes
    carros_por_mes = df_validas['Mes'].value_counts().sort_index()
    st.subheader("🚗 Cantidad de carros por mes")
    st.bar_chart(carros_por_mes)

    # 💰 Pago promedio
    df['Parking_Cost'] = pd.to_numeric(df['Parking_Cost'], errors='coerce')
    pago_promedio = df['Parking_Cost'].mean()
    st.subheader("💰 Pago promedio")
    st.metric("Promedio", f"${pago_promedio:.2f}")

    # 📈 Distribución de tarifas
    st.subheader("📈 Distribución de tarifas")
    conteo_tarifas = df['Parking_Cost'].value_counts().sort_index()
    porcentaje_tarifas = df['Parking_Cost'].value_counts(normalize=True).sort_index() * 100
    tabla_tarifas = pd.DataFrame({
        "Tarifa": conteo_tarifas.index,
        "Cantidad": conteo_tarifas.values,
        "Porcentaje (%)": porcentaje_tarifas.values
    })
    tabla_tarifas_formateada = tabla_tarifas.style.format({
        "Cantidad": "{:,}",
        "Porcentaje (%)": "{:.2f}"
    }).highlight_max(subset=["Cantidad"], color="lightgreen").highlight_min(subset=["Cantidad"], color="lightcoral")
    st.dataframe(tabla_tarifas_formateada)
    st.bar_chart(tabla_tarifas.set_index("Tarifa")["Cantidad"])

    # 📊 Histograma de tarifas
    st.subheader("📊 Histograma de tarifas")
    tarifas_numericas = pd.to_numeric(df['Parking_Cost'], errors='coerce').dropna()
    hist_data = np.histogram(tarifas_numericas, bins=20)
    hist_df = pd.DataFrame({
        "Rango": [f"{round(b,2)}–{round(hist_data[1][i+1],2)}" for i, b in enumerate(hist_data[1][:-1])],
        "Cantidad": hist_data[0]
    })
    st.bar_chart(hist_df.set_index("Rango"))

    # ⏱️ Duración del estacionamiento
    if 'CheckOut_Date' in df.columns:
        df['Duración (hrs)'] = (df['CheckOut_Date'] - df['CheckIn_Date']).dt.total_seconds() / 3600
        duracion_promedio = df['Duración (hrs)'].mean()
        st.subheader("⏱️ Duración promedio")
        st.metric("Promedio", f"{duracion_promedio:.2f} horas")

    # 📥 Exportar datos filtrados
    st.download_button(
        label="📥 Descargar datos filtrados",
        data=df_filtrado.to_csv(index=False).encode('utf-8'),
        file_name="datos_filtrados.csv",
        mime="text/csv"
    )

    # 📋 KPIs por mes
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
    st.dataframe(resumen_kpi.style.format({
        "Pago promedio": "${:,.2f}",
        "Cantidad de carros": "{:,}",
        "Duración promedio": "{:.2f}"
    }))

    # 🚨 Tarifas inusuales
    st.subheader("🚨 Tarifas inusuales")
    umbral = df['Parking_Cost'].quantile(0.95)
    tarifas_altas = df[df['Parking_Cost'] > umbral]
    st.write(f"Se detectaron {len(tarifas_altas)} registros con tarifas superiores al percentil 95 (${umbral:.2f})")
    st.dataframe(tarifas_altas[['CheckIn_Date', 'Parking_Cost']])

    # 📊 Guardar gráficos como imágenes
    fig1, ax1 = plt.subplots()
    carros_por_mes.plot(kind='bar', ax=ax1)
    fig1.savefig("grafico_carros.png", bbox_inches='tight', dpi=300)

    fig2, ax2 = plt.subplots()
    tabla_tarifas.set_index("Tarifa")["Cantidad"].plot(kind='bar', ax=ax2)
    fig2.savefig("grafico_tarifas.png", bbox_inches='tight', dpi=300)

    # 🔁 Convertir imágenes a base64
    grafico_carros_b64 = imagen_base64("grafico_carros.png")
    grafico_tarifas_b64 = imagen_base64("grafico_tarifas.png")

    # 📄 Generar HTML y ofrecer descarga
    html = generar_html(grafico_carros_b64, grafico_tarifas_b64, resumen_kpi)
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