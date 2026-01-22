import streamlit as st
import pandas as pd
from modules.backend import IrigasiBackend
import io
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET

st.set_page_config(page_title="SIKI - Sistem Irigasi", layout="wide")
st.title("🌊 Sistem Informasi Kinerja Irigasi (SIKI)")

if 'backend' not in st.session_state:
    st.session_state.backend = IrigasiBackend()
app = st.session_state.backend

# --- FUNGSI BANTUAN GIS (PETA) ---
def parse_kml_to_map(kml_file):
    """Membaca file KML dan menggambarnya di Peta Folium"""
    m = folium.Map(location=[-4.5, 103.0], zoom_start=12) # Lokasi default (Sumatra/Lampung kira2)
    
    try:
        # Baca konten file
        kml_content = kml_file.getvalue().decode("utf-8")
        root = ET.fromstring(kml_content)
        
        # Namespace KML biasanya ribet, kita handle basicnya
        namespace = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        count = 0
        # Cari Placemark (Titik/Garis/Area)
        for placemark in root.findall('.//kml:Placemark', namespace):
            name = placemark.find('kml:name', namespace)
            name_text = name.text if name is not None else "Aset Tanpa Nama"
            
            # Coba cari Polygon
            polygon = placemark.find('.//kml:Polygon', namespace)
            linestring = placemark.find('.//kml:LineString', namespace)
            point = placemark.find('.//kml:Point', namespace)
            
            if polygon is not None:
                # Ambil koordinat
                coords_text = polygon.find('.//kml:coordinates', namespace).text
                # Parsing teks koordinat "lon,lat,alt lon,lat,alt ..."
                coords = []
                for c in coords_text.strip().split():
                    lon, lat, _ = map(float, c.split(','))
                    coords.append([lat, lon]) # Folium butuh [Lat, Lon]
                
                folium.Polygon(
                    locations=coords,
                    color="blue",
                    fill=True,
                    fill_opacity=0.4,
                    popup=name_text,
                    tooltip=name_text
                ).add_to(m)
                count += 1
                
            elif linestring is not None:
                coords_text = linestring.find('.//kml:coordinates', namespace).text
                coords = []
                for c in coords_text.strip().split():
                    lon, lat, _ = map(float, c.split(','))
                    coords.append([lat, lon])
                
                folium.PolyLine(
                    locations=coords,
                    color="red",
                    weight=4,
                    popup=name_text,
                    tooltip=name_text
                ).add_to(m)
                count += 1

        return m, f"Berhasil memuat {count} aset irigasi dari KML!"
        
    except Exception as e:
        return m, f"Gagal baca KML: {e}"

# --- SIDEBAR: BACKUP & RESTORE (JSON) ---
st.sidebar.divider()
st.sidebar.header("💾 Backup Data (JSON)")
# Tombol Save
json_data = app.export_ke_json()
st.sidebar.download_button(
    label="⬇️ Save File (Download JSON)",
    data=json_data,
    file_name="backup_irigasi.json",
    mime="application/json",
    help="Klik ini untuk menyimpan data ke komputer Kakak."
)

# Tombol Open
uploaded_json = st.sidebar.file_uploader("⬆️ Open File (Restore JSON)", type=["json"])
if uploaded_json is not None:
    if st.sidebar.button("Jalankan Restore"):
        pesan = app.import_dari_json(uploaded_json)
        if "Berhasil" in pesan:
            st.sidebar.success(pesan)
            st.rerun()
        else:
            st.sidebar.error(pesan)

# --- MENU UTAMA ---
menu = st.sidebar.radio("Menu Navigasi", ["Dashboard", "Input Data", "Peta Digital (GIS)", "Analisa Kinerja", "Export Laporan"])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.header("Ringkasan Daerah Irigasi")
    df = app.get_data()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Aset", f"{len(df)} Unit")
    col2.metric("Rata-rata Kinerja", f"{df['nilai_kinerja'].mean() if not df.empty else 0:.2f}%")
    col3.metric("Rusak Berat", f"{len(df[df['nilai_kinerja'] < 60]) if not df.empty else 0} Unit")

# --- INPUT DATA ---
elif menu == "Input Data":
    st.header("Manajemen Data Aset")
    tab1, tab2 = st.tabs(["📝 Tambah Manual", "📊 Edit Tabel"])
    
    with tab1:
        with st.form("form_tambah"):
            c1, c2 = st.columns(2)
            with c1:
                nama = st.text_input("Nama Aset")
                jenis = st.selectbox("Jenis", ["Saluran Primer", "Saluran Sekunder", "Bendung", "Bangunan Bagi", "Sawah"])
                kmz = st.file_uploader("Upload KMZ/KML (Untuk Database)", type=['kml', 'kmz'])
            with c2:
                satuan = st.selectbox("Satuan", ["m", "bh", "unit", "ha"])
                b = st.number_input("Kondisi Baik", min_value=0.0)
                rr = st.number_input("Rusak Ringan", min_value=0.0)
                rb = st.number_input("Rusak Berat", min_value=0.0)
            
            if st.form_submit_button("Simpan"):
                msg = app.tambah_data_baru(nama, jenis, satuan, b, rr, rb, kmz)
                st.success(msg)
    
    with tab2:
        df = app.get_data()
        edited = st.data_editor(df, num_rows="dynamic", hide_index=True, use_container_width=True)
        if st.button("Simpan Tabel"):
            app.update_data(edited)
            st.success("Tersimpan!")
            st.rerun()

# --- PETA DIGITAL (GIS) ---
elif menu == "Peta Digital (GIS)":
    st.header("🗺️ Peta Jaringan Irigasi")
    st.info("Upload file KML/KMZ untuk melihat jaringan irigasi di peta.")
    
    file_peta = st.file_uploader("Pilih File KML", type=["kml"])
    
    if file_peta:
        peta, pesan = parse_kml_to_map(file_peta)
        if "Berhasil" in pesan:
            st.success(pesan)
            # Tampilkan Peta Full Width
            st_folium(peta, width=1000, height=500)
        else:
            st.error(pesan)
    else:
        # Peta Kosong Default
        m_default = folium.Map(location=[-4.5, 103.0], zoom_start=9)
        st_folium(m_default, width=1000, height=500)

# --- ANALISA ---
elif menu == "Analisa Kinerja":
    st.header("Prioritas Penanganan")
    df = app.get_data()
    if not df.empty:
        rusak = df[df['nilai_kinerja'] < 60]
        if not rusak.empty:
            st.error(f"Ada {len(rusak)} aset Rusak Berat!")
            st.dataframe(rusak)
        else:
            st.success("Semua aset Kondisi Aman.")

# --- EXPORT ---
elif menu == "Export Laporan":
    st.header("Download Laporan Excel")
    if st.button("Download"):
        df = app.get_data()
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        st.download_button("Klik Download", buffer, "Laporan_SIKI.xlsx")
