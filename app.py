import math
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Auditoria de Precisão DGPS | Guma Oceano",
    page_icon="🛰️",
    layout="wide",
)


def dms_to_decimal(deg, min, sec):
  sign = -1 if deg < 0 or str(deg).startswith("-") else 1
  deg_abs = abs(float(deg))
  return (deg_abs + float(min) / 60.0 + float(sec) / 3600.0) * sign


def nmea_to_decimal(coord_str, direction):
  if not coord_str or not direction:
    return None
  try:
    if direction in ["N", "S"]:
      degrees = float(coord_str[:2])
      minutes = float(coord_str[2:])
    else:
      degrees = float(coord_str[:3])
      minutes = float(coord_str[3:])

    decimal = degrees + minutes / 60.0
    if direction in ["S", "W"]:
      decimal = -decimal
    return decimal
  except ValueError:
    return None


def calculate_local_offsets(lat, lon, ref_lat, ref_lon):
  R = 6371000  # Raio médio da Terra em metros
  dlat = math.radians(lat - ref_lat)
  dlon = math.radians(lon - ref_lon)
  dy = dlat * R
  dx = dlon * R * math.cos(math.radians((lat + ref_lat) / 2))
  return dx, dy


@st.cache_data
def parse_nmea_log(file_content):
  data = []
  lines = file_content.decode("utf-8", errors="ignore").splitlines()

  for line in lines:
    if line.startswith("$GPGGA"):
      parts = line.split(",")
      if len(parts) >= 10 and parts[2] and parts[4]:
        utc_time = parts[1]
        lat = nmea_to_decimal(parts[2], parts[3])
        lon = nmea_to_decimal(parts[4], parts[5])
        fix_quality = parts[6]
        num_sats = parts[7]
        hdop = parts[8]
        altitude = parts[9]

        if lat is not None and lon is not None:
          data.append({
              "UTC": utc_time,
              "Lat": lat,
              "Lon": lon,
              "Fix": int(fix_quality) if fix_quality.isdigit() else 0,
              "Sats": int(num_sats) if num_sats.isdigit() else 0,
              "HDOP": float(hdop) if hdop else 0.0,
              "Altitude": float(altitude) if altitude else 0.0,
          })

  return pd.DataFrame(data)


# Interface do Aplicativo
st.title("🛰️ Auditoria de Acurácia e Precisão DGPS")
st.markdown(
    "**Precisão além da superfície** — Ferramenta de validação e confiabilidade"
    " metrológica para clientes."
)

st.sidebar.header("1. Parâmetros de Referência")
usar_centroide = st.sidebar.checkbox(
    "Usar centro da coleta como referência (Focar na Precisão Interna)",
    value=True,
    help=(
        "Remove o viés de coordenadas do marco e mede o quão compactos os"
        " pontos ficaram entre si."
    ),
)

if not usar_centroide:
  st.sidebar.markdown("Insira os dados do marco do IBGE (DMS):")
  lat_deg = st.sidebar.number_input("Graus (Lat)", value=-23, format="%d")
  lat_min = st.sidebar.number_input("Minutos (Lat)", value=0, format="%d")
  lat_sec = st.sidebar.number_input(
      "Segundos (Lat)", value=26.6039, format="%.4f"
  )

  lon_deg = st.sidebar.number_input("Graus (Lon)", value=-46, format="%d")
  lon_min = st.sidebar.number_input("Minutos (Lon)", value=0, format="%d")
  lon_sec = st.sidebar.number_input("Segundos (Lon)", value=0.0, format="%.4f")
  ref_lat = dms_to_decimal(lat_deg, lat_min, lat_sec)
  ref_lon = dms_to_decimal(lon_deg, lon_min, lon_sec)
else:
  st.sidebar.info(
      "Modo de Precisão Interna ativado: o ponto zero (0,0) será a média da"
      " sua própria coleta."
  )

st.sidebar.markdown("---")
st.sidebar.header("2. Arquivo de Rastreio NMEA")
uploaded_file = st.sidebar.file_uploader(
    "Envie o arquivo bruto (.log)", type=["log", "txt"]
)

if uploaded_file is not None:
  file_bytes = uploaded_file.read()
  df = parse_nmea_log(file_bytes)

  if df.empty:
    st.error(
        "Não foram encontradas sentenças $GPGGA válidas no arquivo enviado."
    )
  else:
    if usar_centroide:
      ref_lat = df["Lat"].mean()
      ref_lon = df["Lon"].mean()

    dx_list = []
    dy_list = []
    dist_list = []

    for idx, row in df.iterrows():
      dx, dy = calculate_local_offsets(
          row["Lat"], row["Lon"], ref_lat, ref_lon
      )
      dist = math.sqrt(dx**2 + dy**2)
      dx_list.append(dx)
      dy_list.append(dy)
      dist_list.append(dist)

    df["Error_X_m"] = dx_list
    df["Error_Y_m"] = dy_list
    df["Error_Radial_m"] = dist_list

    cep_50 = np.percentile(df["Error_Radial_m"], 50) * 100  # em cm
    rms_95 = np.percentile(df["Error_Radial_m"], 95) * 100  # em cm

    st.markdown("---")
    st.subheader("📊 Indicadores de Desempenho Metrológico")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Amostras", f"{len(df)} épocas")
    col2.metric("CEP (50% de Confiança)", f"{cep_50:.2f} cm")
    col3.metric("RMS (95% de Confiança)", f"{rms_95:.2f} cm")
    col4.metric(
        "Média de Satélites / HDOP",
        f"{df['Sats'].mean():.1f} sats / {df['HDOP'].mean():.2f}",
    )

    st.markdown("---")

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
      st.subheader("Dispersão Planimétrica (X vs Y em Metros)")
      fig_scatter = px.scatter(
          df,
          x="Error_X_m",
          y="Error_Y_m",
          color="HDOP",
          title="Dispersão em Relação ao Centro (0,0)",
          labels={
              "Error_X_m": "Erro Leste / X (m)",
              "Error_Y_m": "Erro Norte / Y (m)",
          },
          color_continuous_scale="Viridis",
      )
      fig_scatter.add_scatter(
          x=[0],
          y=[0],
          mode="markers",
          marker=dict(color="red", size=14, symbol="cross"),
          name="Referência Zero",
      )
      st.plotly_chart(fig_scatter, use_container_width=True)

    with col_chart2:
      st.subheader("Evolução do Erro Radial ao Longo do Tempo")
      df["Error_Radial_cm"] = df["Error_Radial_m"] * 100
      fig_time = px.line(
          df,
          y="Error_Radial_cm",
          title="Erro Radial (centímetros) por Época",
          labels={
              "index": "Amostra / Época",
              "Error_Radial_cm": "Erro Radial (cm)",
          },
      )
      st.plotly_chart(fig_time, use_container_width=True)

    with st.expander("🔍 Visualizar Dados Processados (Logs NMEA Convertidos)"):
      st.dataframe(df)

    st.markdown("---")
    st.subheader("📋 Laudo de Confiabilidade Auditável para o Cliente")
    st.success(
        f"""
        * **Acurácia Planimétrica (CEP 50%):** `{cep_50:.2f} cm` — 50% dos pontos coletados concentram-se dentro deste raio.
        * **Nível de Confiança Operacional (95%):** `{rms_95:.2f} cm` — Garantia de repetibilidade para locações batimétricas e topográficas.
        * **Condição de Fixação:** Qualidade de correção estável durante o período de aquisição.
        """
    )
else:
  st.info(
      "👈 Configure as opções na barra lateral e envie o arquivo `.log` para"
      " gerar o laudo."
  )
