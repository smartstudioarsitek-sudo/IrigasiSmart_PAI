import streamlit as st
import pandas as pd
import altair as alt  # Library Grafik Bagus
from modules.backend import IrigasiBackend
import io
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET

st.set_page_config(page_title="IKSI - Sistem Irigasi", layout="wide")
st.title("🌊  Informasi Kinerja Sistem Irigasi (IKSI)")

if 'backend' not in st.session_state:
    st.session_state.backend = IrigasiBackend()
app = st.session_state.backend

# --- FUNGSI PETA ---
def parse_kml_to_map(kml_file):
    m = folium.Map(location=[-4.5, 103.0], zoom_start=12)
    try:
        kml_content = kml_file.getvalue().decode("utf-8")
        root = ET.fromstring(kml_content)
        namespace = {'kml': 'http://www.opengis.net/kml/2.2'}
        count = 0
        for placemark in root.findall('.//kml:Placemark', namespace):
            name = placemark.find('kml:name', namespace)
            name_text = name.text if name is not None else "Aset"
            
            # Simple Geometry Parser
            for geom in ['Polygon', 'LineString', 'Point']:
                obj = placemark.find(f'.//kml:{geom}', namespace)
                if obj:
                    coords_text = obj.find('.//kml:coordinates', namespace).text
                    coords = []
                    for c in coords_text.strip().split():
                        lon, lat, *_ = map(float, c.split(','))
                        coords.append([lat, lon])
                    
                    if geom == 'Polygon':
                        folium.Polygon(coords, color="blue", fill=True, popup=name_text).add_to(m)
                    elif geom == 'LineString':
                        folium.PolyLine(coords, color="red", weight=4, popup=name_text).add_to(m)
                    elif geom == 'Point':
                        folium.Marker(coords[0], popup=name_text).add_to(m)
                    count += 1
        return m, f"Memuat {count} aset."
    except Exception as e:
        return m, f"Gagal baca: {e}"

# --- SIDEBAR: MENU TEKNISI (RESET) ---
st.sidebar.divider()
with st.sidebar.expander("🛠️ Menu Teknisi (Reset)"):
    st.warning("Zona Berbahaya!")
    if st.button("⚠️ HAPUS SEMUA DATA (RESET)"):
        pesan = app.hapus_semua_data()
        st.success(pesan)
        st.rerun()

# --- SIDEBAR: BACKUP ---
json_data = app.export_ke_json()
st.sidebar.download_button("⬇️ Backup JSON", json_data, "backup.json", "application/json")
uploaded_json = st.sidebar.file_uploader("⬆️ Restore JSON", type=["json"])
if uploaded_json and st.sidebar.button("Restore Sekarang"):
    app.import_dari_json(uploaded_json)
    st.rerun()

# --- MENU UTAMA ---
menu = st.sidebar.radio("Menu Navigasi", ["Dashboard", "Input Data", "Peta Digital (GIS)", "Analisa Kinerja", "Export Laporan"])

# --- DASHBOARD GRAFIK BAGUS ---
if menu == "Dashboard":
    st.header("Dashboard Kinerja Irigasi")
    df = app.get_data()
    
    # Metrik Utama
    c1, c2, c3, c4 = st.columns(4)
    total = len(df)
    rata = df['nilai_kinerja'].mean() if not df.empty else 0
    baik = len(df[df['nilai_kinerja'] >= 80])
    rusak = len(df[df['nilai_kinerja'] < 60])
    
    c1.metric("Total Aset", f"{total} Unit")
    c2.metric("Rata-rata Kinerja", f"{rata:.1f}%")
    c3.metric("Kondisi Baik", f"{baik} Unit", delta="Aman")
    c4.metric("Rusak Berat", f"{rusak} Unit", delta_color="inverse", delta=f"-{rusak}")

    st.divider()

    if not df.empty:
        col_grafik1, col_grafik2 = st.columns(2)
        
        with col_grafik1:
            st.subheader("📊 Rata-rata Kinerja per Jenis")
            # Grafik Batang Horizontal (Bar Chart)
            chart_bar = alt.Chart(df).mark_bar().encode(
                x=alt.X('mean(nilai_kinerja)', title='Nilai Kinerja (%)'),
                y=alt.Y('jenis_aset', sort='-x', title='Jenis Aset'),
                color=alt.Color('mean(nilai_kinerja)', scale=alt.Scale(scheme='greens'), legend=None),
                tooltip=['jenis_aset', 'mean(nilai_kinerja)']
            ).interactive()
            st.altair_chart(chart_bar, use_container_width=True)

        with col_grafik2:
            st.subheader("🍩 Komposisi Kondisi Aset")
            # Kategorisasi Data untuk Donut Chart
            def kategori(n):
                if n >= 80: return 'Baik'
                elif n >= 60: return 'Rusak Ringan'
                else: return 'Rusak Berat'
            
            df['Status'] = df['nilai_kinerja'].apply(kategori)
            df_pie = df['Status'].value_counts().reset_index()
            df_pie.columns = ['Status', 'Jumlah']
            
            # Grafik Donut
            base = alt.Chart(df_pie).encode(theta=alt.Theta("Jumlah", stack=True))
            pie = base.mark_arc(outerRadius=120, innerRadius=60).encode(
                color=alt.Color("Status", scale=alt.Scale(domain=['Baik', 'Rusak Ringan', 'Rusak Berat'], range=['#2ecc71', '#f1c40f', '#e74c3c'])),
                order=alt.Order("Jumlah", sort="descending"),
                tooltip=["Status", "Jumlah"]
            )
            text = base.mark_text(radius=140).encode(
                text="Jumlah",
                order=alt.Order("Jumlah", sort="descending"),
                color=alt.value("black") 
            )
            st.altair_chart(pie + text, use_container_width=True)
            
    else:
        st.info("Belum ada data untuk ditampilkan grafiknya.")

# --- INPUT DATA ---
elif menu == "Input Data":
    st.header("Input Data Inventaris")
    t1, t2 = st.tabs(["📝 Form Input", "✏️ Edit Tabel"])
    with t1:
        with st.form("add"):
            c1,c2 = st.columns(2)
            with c1:
                nm = st.text_input("Nama Aset")
                jn = st.selectbox("Jenis", ["Saluran Primer", "Saluran Sekunder", "Bendung", "Bangunan Bagi", "Sawah"])
                kmz = st.file_uploader("Upload Peta (KMZ)", type=['kml','kmz'])
            with c2:
                sat = st.selectbox("Satuan", ["m", "bh", "unit"])
                b = st.number_input("Baik", min_value=0.0)
                rr = st.number_input("Rusak Ringan", min_value=0.0)
                rb = st.number_input("Rusak Berat", min_value=0.0)
            if st.form_submit_button("Simpan"):
                st.success(app.tambah_data_baru(nm, jn, sat, b, rr, rb, kmz))
    with t2:
        df = app.get_data()
        ed = st.data_editor(df, hide_index=True, use_container_width=True)
        if st.button("Update Tabel"):
            app.update_data(ed)
            st.rerun()

# --- PETA ---
elif menu == "Peta Digital (GIS)":
    st.header("Peta Jaringan Irigasi")
    up = st.file_uploader("Upload KML", type=["kml"])
    if up:
        m, msg = parse_kml_to_map(up)
        st.success(msg)
        st_folium(m, width=1000, height=500)
    else:
        st_folium(folium.Map([-4.5, 103.0], zoom_start=9), width=1000, height=500)

# --- ANALISA ---
elif menu == "Analisa Kinerja":
    st.header("Analisa Prioritas")
    df = app.get_data()
    if not df.empty:
        df_rb = df[df['nilai_kinerja'] < 60]
        if not df_rb.empty:
            st.error(f"Perhatian: {len(df_rb)} Aset Rusak Berat!")
            st.dataframe(df_rb)
        else:
            st.success("Semua aset dalam kondisi baik.")

# --- EXPORT ---
elif menu == "Export Laporan":
    if st.button("Download Excel"):
        df = app.get_data()
        b = io.BytesIO()
        with pd.ExcelWriter(b, engine='xlsxwriter') as w:
            df.to_excel(w, index=False)
        st.download_button("Download", b, "Laporan.xlsx")

