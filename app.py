import io
import math
from fpdf import FPDF
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


# Classe para gerar o PDF formatado
class PDFReport(FPDF):

  def header(self):
    self.set_font("helvetica", "B", 14)
    self.set_text_color(10, 30, 60)
    self.cell(
        0,
        10,
        "GUMA OCEANO - Laudo de Auditoria Metrológica DGPS",
        0,
        1,
        "C",
    )
    self.set_font("helvetica", "I", 9)
    self.set_text_color(100, 100, 100)
    self.cell(
        0, 5, "Precisão além da superfície — Relatório de Acurácia Absoluta", 0, 1, "C"
    )
    self.ln(5)

  def footer(self):
    self.set_y(-15)
    self.set_font("helvetica", "I", 8)
    self.set_text_color(150, 150, 150)
    self.cell(
        0, 10, f"Página {self.page_no()} | Gerado via Sistema Guma Oceano", 0, 0, "C"
    )


def generate_pdf_report(
    cep_50, rms_95, total_sats, mean_hdop, total_epochs, ref_lat, ref_lon
):
  pdf = PDFReport()
  pdf.add_page()
  pdf.set_font("helvetica", "", 10)

  # Seção de Informações
  pdf.set_font("helvetica", "B", 11)
  pdf.set_fill_color(230, 240, 250)
  pdf.cell(0, 8, " 1. Parâmetros de Referência e Geodésia", 0, 1, "L", True)
  pdf.set_font("helvetica", "", 10)
  pdf.cell(
      0,
      6,
      f"Coordenada de Referência (Marco): Lat {ref_lat:.6f}, Lon"
      f" {ref_lon:.6f}",
      0,
      1,
  )
  pdf.cell(0, 6, f"Total de Épocas Analisadas: {total_epochs} amostras", 0, 1)
  pdf.ln(4)

  # Seção de Indicadores
  pdf.set_font("helvetica", "B", 11)
  pdf.fill_color = (230, 240, 250)
  pdf.cell(0, 8, " 2. Indicadores de Desempenho Metrológico", 0, 1, "L", True)
  pdf.set_font("helvetica", "", 10)
  pdf.cell(
      0,
      6,
      f"Acurácia Planimétrica (CEP 50%): {cep_50:.2f} cm (Raio de concentração"
      " central)",
      0,
      1,
  )
  pdf.cell(
      0,
      6,
      f"Nível de Confiança Operacional (RMS 95%): {rms_95:.2f} cm (Repetibilidade"
      " para batimetria)",
      0,
      1,
  )
  pdf.cell(
      0,
      6,
      f"Condição de Sinal: Média de {total_sats:.1f} satélites | HDOP médio de"
      f" {mean_hdop:.2f}",
      0,
      1,
  )
  pdf.ln(4)

  # Seção de Descrição Metodológica
  pdf.set_font("helvetica", "B", 11)
  pdf.fill_color = (230, 240, 250)
  pdf.cell(0, 8, " 3. Descrição Metodológica e Confiabilidade", 0, 1, "L", True)
  pdf.set_font("helvetica", "", 9)

  desc_text = (
      "O presente relatório atesta a auditoria de acurácia planimétrica de"
      " posicionamento DGPS coletado em campo. O processamento converteu as"
      " sentenças NMEA brutas ($GPGGA) para o sistema métrico local em relação"
      " ao marco de referência conhecido cadastrado. O CEP (Circular Error"
      " Probable) de 50% demonstra a dispersão central dos dados, enquanto o"
      " RMS de 95% assegura a confiabilidade e robustez exigidas para"
      " levantamentos hidrográficos e geofísicos de alta precisão."
  )
  pdf.multi_cell(0, 5, desc_text)
  pdf.ln(10)

  pdf.set_font("helvetica", "I", 9)
  pdf.cell(
      0,
      6,
      "Documento gerado eletronicamente para fins de comprovação técnica junto"
      " a clientes e contratantes.",
      0,
      1,
      "C",
  )

  return pdf.output()


# Interface do Aplicativo
st.title("🛰️ Auditoria de Acurácia e Precisão DGPS")
st.markdown(
    "**Precisão além da superfície** — Ferramenta de validação e confiabilidade"
    " metrológica para clientes."
)

st.sidebar.header("1. Coordenada do Marco Conhecido (Padrão IBGE)")
st.sidebar.markdown("Insira os dados da monografia do marco geodésico:")

lat_deg = st.sidebar.number_input("Graus (Lat)", value=-23, format="%d")
lat_min = st.sidebar.number_input("Minutos (Lat)", value=0, format="%d")
lat_sec = st.sidebar.number_input("Segundos (Lat)", value=26.6039, format="%.4f")

st.sidebar.markdown("---")
lon_deg = st.sidebar.number_input("Graus (Lon)", value=-46, format="%d")
lon_min = st.sidebar.number_input("Minutos (Lon)", value=0, format="%d")
lon_sec = st.sidebar.number_input("Segundos (Lon)", value=0.0, format="%.4f")

ref_lat = dms_to_decimal(lat_deg, lat_min, lat_sec)
ref_lon = dms_to_decimal(lon_deg, lon_min, lon_sec)

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

    cep_50 = np.percentile(df["Error_Radial_m"], 50) * 100
    rms_95 = np.percentile(df["Error_Radial_m"], 95) * 100
    mean_sats = df["Sats"].mean()
    mean_hdop = df["HDOP"].mean()

    st.markdown("---")
    st.subheader("📊 Indicadores de Desempenho Metrológico")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Amostras", f"{len(df)} épocas")
    col2.metric("CEP (50% de Confiança)", f"{cep_50:.2f} cm")
    col3.metric("RMS (95% de Confiança)", f"{rms_95:.2f} cm")
    col4.metric("Média de Satélites / HDOP", f"{mean_sats:.1f} / {mean_hdop:.2f}")

    st.markdown("---")

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
          marker=dict(color="red", size=14, symbol="cross"),
          name="Marco Conhecido (IBGE)",
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

    # Botão para gerar e baixar o Relatório PDF
    st.markdown("---")
    st.subheader("📄 Geração de Laudo Técnico Auditável")
    if st.button("Gerar Relatório Técnico em PDF"):
      pdf_data = generate_pdf_report(
          cep_50,
          rms_95,
          mean_sats,
          mean_hdop,
          len(df),
          ref_lat,
          ref_lon,
      )
      st.download_button(
          label="⬇️ Baixar Laudo PDF para o Cliente",
          data=pdf_data,
          file_name="Laudo_Auditoria_DGPS_GumaOceano.pdf",
          mime="application/pdf",
      )

    with st.expander("🔍 Visualizar Dados Processados (Logs NMEA Convertidos)"):
      st.dataframe(df)
else:
  st.info(
      "👈 Insira as coordenadas do marco do IBGE na barra lateral e envie o"
      " arquivo `.log` para habilitar a geração do relatório."
  )
