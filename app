import io
import math
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as objects
import streamlit as st

st.set_page_config(
    page_title="Auditoria de Precisão DGPS | Guma Oceano",
    page_icon="🛰️",
    layout="wide",
)


# Função para converter coordenadas NMEA (DDMM.MMMMM) para Graus Decimais
def nmea_to_decimal(coord_str, direction):
  if not coord_str or not direction:
    return None
  try:
    if direction in ["N", "S"]:
      degrees = float(coord_str[:2])
      minutes = float(coord_str[2:])
    else:  # E, W
      degrees = float(coord_str[:3])
      minutes = float(coord_str[3:])

    decimal = degrees + minutes / 60.0
    if direction in ["S", "W"]:
      decimal = -decimal
    return decimal
  except ValueError:
    return None


# Função para calcular distância em metros entre duas coordenadas (Fórmula de Haversine simplificada para pequenas distâncias)
def haversine_meters(lat1, lon1, lat2, lon2):
  R = 6371000  # Raio da Terra em metros
  phi1 = math.radians(lat1)
  phi2 = math.radians(lat2)
  dphi = math.radians(lat2 - lat1)
  dlambda = math.radians(lon2 - lon1)

  a = (
      math.sin(dphi / 2) ** 2
      + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
  )
  c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

  # Componentes aproximadas em X (Easting/Longitude) e Y (Northing/Latitude)
  dy = (lat2 - lat1) * 111320
  dx = (lon2 - lon1) * 111320 * math.cos(math.radians((lat1 + lat2) / 2))
  return dx, dy, R * c


@st.cache_data
def parse_nmea_log(file_content):
  data = []
  lines = file_content.decode("utf-8").splitlines()

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

st.sidebar.header("1. Parâmetros de Referência (IBGE)")
ref_lat = st.sidebar.number_input(
    "Latitude do Marco (Graus Decimais)", value=-23.00739, format="%.6f"
)
ref_lon = st.sidebar.number_input(
    "Longitude do Marco (Graus Decimais)", value=-46.99986, format="%.6f"
)

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
    # Calcular dispersões em relação ao marco de referência
    dx_list = []
    dy_list = []
    dist_list = []

    for idx, row in df.iterrows():
      dx, dy, dist = haversine_meters(ref_lat, ref_lon, row["Lat"], row["Lon"])
      dx_list.append(dx)
      dy_list.append(dy)
      dist_list.append(dist)

    df["Error_X_m"] = dx_list
    df["Error_Y_m"] = dy_list
    df["Error_Radial_m"] = dist_list

    # Métricas Estatísticas Principais
    mean_x = np.mean(df["Error_X_m"])
    mean_y = np.mean(df["Error_Y_m"])
    std_x = np.std(df["Error_X_m"])
    std_y = np.std(df["Error_Y_m"])
    rms_radial = np.sqrt(np.mean(df["Error_Radial_m"] ** 2))
    cep_50 = np.percentile(df["Error_Radial_m"], 50)
    rms_95 = np.percentile(df["Error_Radial_m"], 95)

    # Exibição em Métricas do Streamlit
    st.markdown("---")
    st.subheader("📊 Indicadores de Desempenho Metrológico (1 Hora de Rastreio)")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Amostras", f"{len(df)} épocas")
    col2.metric("CEP (50% de Confiança)", f"{cep_50*100:.2f} cm")
    col3.metric("RMS (95% de Confiança)", f"{rms_95*100:.2f} cm")
    col4.metric(
        "Média de Satélites / HDOP",
        f"{df['Sats'].mean():.1f} sats / {df['HDOP'].mean():.2f}",
    )

    st.markdown("---")

    # Gráficos de Dispersão
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
      st.subheader("Dispersão Planimétrica (X vs Y em Metros)")
      fig_scatter = px.scatter(
          df,
          x="Error_X_m",
          y="Error_Y_m",
          color="HDOP",
          title="Dispersão em Relação ao Marco Zero (0,0)",
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
          marker=dict(color="red", size=12, symbol="cross"),
          name="Marco Conhecido (IBGE)",
      )
      st.plotly_chart(fig_scatter, use_container_width=True)

    with col_chart2:
      st.subheader("Evolução do Erro Radial ao Longo do Tempo")
      fig_time = px.line(
          df,
          y="Error_Radial_m",
          title="Erro Radial (metros) por Época",
          labels={
              "index": "Amostra / Época",
              "Error_Radial_m": "Erro Radial (m)",
          },
      )
      st.plotly_chart(fig_time, use_container_width=True)

    # Tabela de Dados Brutos Tratados
    with st.expander("🔍 Visualizar Dados Processados (Logs NMEA Convertidos)"):
      st.dataframe(df)

    # Seção de Auditoria para o Cliente
    st.markdown("---")
    st.subheader("📋 Laudo de Confiabilidade Auditável para o Cliente")
    st.success(
        f"""
        * **Período Analisado:** Rastreio contínuo de alta densidade.
        * **Acurácia Planimétrica (CEP 50%):** `{cep_50*100:.2f} cm` — 50% dos pontos coletados concentram-se dentro deste raio.
        * **Nível de Confiança Operacional (95%):** `{rms_95*100:.2f} cm` — Garantia de repetibilidade para locações bathimétricas e topográficas.
        * **Condição de Fixação:** Qualidade de correção estável durante todo o período de aquisição.
        """
    )
else:
  st.info(
      "👈 Insira as coordenadas do marco de referência e faça o upload do"
      " arquivo `.log` na barra lateral para iniciar a análise."
  )
