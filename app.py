import streamlit as st
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET
import io
from modules.backend import IrigasiBackend

# Config Halaman
st.set_page_config(page_title="SIKI - Sistem Irigasi", layout="wide")
st.title("🌊 Sistem Informasi Kinerja Irigasi (SIKI)")

if 'backend' not in st.session_state:
    st.session_state.backend = IrigasiBackend()
app = st.session_state.backend

# --- FUNGSI PETA GIS ---
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
            
            for geom in ['Polygon', 'LineString', 'Point']:
                obj = placemark.find(f'.//kml:{geom}', namespace)
                if obj:
                    coords_text = obj.find('.//kml:coordinates', namespace).text
                    coords = []
                    for c in coords_text.strip().split():
                        lon, lat, *_ = map(float, c.split(','))
                        coords.append([lat, lon])
                    
                    if geom == 'Polygon': folium.Polygon(coords, color="blue", fill=True, popup=name_text).add_to(m)
                    elif geom == 'LineString': folium.PolyLine(coords, color="red", weight=4, popup=name_text).add_to(m)
                    elif geom == 'Point': folium.Marker(coords[0], popup=name_text).add_to(m)
                    count += 1
        return m, f"Memuat {count} aset."
    except Exception as e: return m, f"Gagal: {e}"

# --- FUNGSI GAMBAR SKETSA ---
def gambar_sketsa(jenis, params):
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.set_axis_off()
    if "Saluran" in jenis:
        b, h, m = params.get('b', 1.0), params.get('h', 1.0), params.get('m', 1.0)
        x = [0, m*h, m*h + b, 2*m*h + b]
        y = [h, 0, 0, h]
        ax.plot(x, y, 'k-', linewidth=2)
        ax.plot([x[0]-1, x[3]+1], [h, h], 'g--', linewidth=1, label="Muka Tanah")
        ax.text((m*h + b/2), -0.2, f"b = {b} m", ha='center', color='blue')
        ax.set_title(f"Sketsa Penampang ({params.get('tipe_lining','Tanah')})")
    elif "Bendung" in jenis:
        H = params.get('tinggi_mercu', 2)
        polygon = patches.Polygon([[0, 0], [2, H], [4, 0]], closed=True, edgecolor='black', facecolor='gray')
        ax.add_patch(polygon)
        ax.text(2, H/2, f"H = {H} m", ha='center', color='white')
        ax.set_title("Sketsa Bendung")
    else:
        ax.text(0.5, 0.5, "Visualisasi belum tersedia", ha='center')
    return fig

# --- SIDEBAR: JSON & RESET ---
st.sidebar.divider()
with st.sidebar.expander("🛠️ Menu Teknisi (Reset & Backup)"):
    if st.button("⚠️ RESET SEMUA DATA"):
        st.success(app.hapus_semua_data())
        st.rerun()
    st.divider()
    json_data = app.export_ke_json()
    st.download_button("⬇️ Backup JSON", json_data, "backup.json", "application/json")
    up_json = st.file_uploader("⬆️ Restore JSON", type=["json"])
    if up_json and st.button("Restore Sekarang"):
        st.success(app.import_dari_json(up_json))
        st.rerun()

# --- MENU NAVIGASI ---
menu = st.sidebar.radio("Menu Navigasi", [
    "Dashboard", 
    "Input Aset Fisik", 
    "Input Data Non-Fisik", 
    "Peta Digital (GIS)", 
    "Analisa & Export"
])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.header("Ringkasan Daerah Irigasi")
    df = app.get_data()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Aset Fisik", f"{len(df)} Unit")
    c2.metric("Rata-rata Kinerja", f"{df['nilai_kinerja'].mean() if not df.empty else 0:.1f}%")
    df_p3a = app.get_table_data('data_p3a')
    c3.metric("Jumlah P3A", f"{len(df_p3a)} Kelompok")
    
    st.divider()
    if not df.empty:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("Grafik Kinerja")
            st.bar_chart(df['nilai_kinerja'])
        with col_g2:
            st.subheader("Komposisi Kerusakan")
            rusak = len(df[df['nilai_kinerja'] < 60])
            baik = len(df) - rusak
            st.write(pd.DataFrame({'Kondisi': ['Baik/RR', 'Rusak Berat'], 'Jumlah': [baik, rusak]}).set_index('Kondisi'))

# --- INPUT ASET FISIK (DENGAN UPLOAD KMZ) ---
elif menu == "Input Aset Fisik":
    st.header("📝 Input Data Prasarana Fisik")
    t1, t2 = st.tabs(["Formulir Detail", "Data Tabel"])
    with t1:
        c1, c2 = st.columns([1, 1])
        with c1:
            jenis = st.selectbox("Jenis:", ["Saluran (Primer/Sekunder)", "Bendung", "Bangunan Bagi", "Lainnya"])
            nama = st.text_input("Nama Aset")
            
            # --- FITUR DIKEMBALIKAN: UPLOAD PETA DI FORM ---
            file_peta = st.file_uploader("Upload Peta (KMZ/KML) - Opsional", type=["kmz", "kml"])
            # -----------------------------------------------
            
            detail = {}
            if "Saluran" in jenis:
                b = st.number_input("Lebar Dasar (b)", min_value=0.0, value=1.0, step=0.05, format="%.2f")
                h = st.number_input("Tinggi Jagaan (h)", min_value=0.0, value=1.0, step=0.05, format="%.2f")
                m = st.number_input("Kemiringan (m)", min_value=0.0, value=1.0, step=0.05, format="%.2f")
                detail = {"b":b, "h":h, "m":m, "tipe_lining": st.selectbox("Lining", ["Tanah","Beton"])}
                sat = "m"
            elif "Bendung" in jenis:
                H = st.number_input("Tinggi Mercu (m)", min_value=0.0, value=2.0, step=0.05, format="%.2f")
                detail = {"tinggi_mercu":H}
                sat = "bh"
            else: sat = "unit"
        with c2:
            st.pyplot(gambar_sketsa(jenis, detail))
            st.divider()
            cb = st.number_input("Baik", min_value=0.0)
            crr = st.number_input("RR", min_value=0.0)
            crb = st.number_input("RB", min_value=0.0)
            
            if st.button("Simpan Fisik"): 
                # Kirim file_peta ke backend
                st.success(app.tambah_data_kompleks(nama, jenis, sat, cb, crr, crb, detail, file_kmz=file_peta))
    with t2:
        df = app.get_data()
        ed = st.data_editor(df, hide_index=True, use_container_width=True)
        if st.button("Update Tabel"):
            app.update_data(ed)
            st.rerun()

# --- INPUT NON-FISIK ---
elif menu == "Input Data Non-Fisik":
    st.header("📋 Data Penunjang (Non-Fisik)")
    t_tanam, t_p3a, t_sdm = st.tabs(["Tanam", "P3A", "SDM & Sarana"])
    
    with t_tanam:
        with st.form("tanam"):
            c1,c2 = st.columns(2)
            musim = c1.selectbox("Musim", ["MT-1", "MT-2", "MT-3"])
            luas = c2.number_input("Rencana Luas (Ha)", min_value=0.0)
            real = c2.number_input("Realisasi (Ha)", min_value=0.0)
            padi = c1.number_input("Prod. Padi (Ton/Ha)", min_value=0.0)
            palawija = c1.number_input("Prod. Palawija (Ton/Ha)", min_value=0.0)
            if st.form_submit_button("Simpan Tanam"): st.success(app.tambah_data_tanam(musim, luas, real, padi, palawija))
        st.data_editor(app.get_table_data('data_tanam'), key='ed_tanam', num_rows="dynamic")

    with t_p3a:
        with st.form("p3a"):
            nm = st.text_input("Nama P3A")
            ds = st.text_input("Desa")
            stt = st.selectbox("Badan Hukum", ["Sudah", "Belum"])
            akt = st.selectbox("Keaktifan", ["Aktif", "Sedang", "Kurang"])
            ang = st.number_input("Anggota", min_value=0)
            if st.form_submit_button("Simpan P3A"): st.success(app.tambah_data_p3a(nm, ds, stt, akt, ang))
        st.data_editor(app.get_table_data('data_p3a'), key='ed_p3a', num_rows="dynamic")
        
    with t_sdm:
        with st.form("sdm"):
            jns = st.selectbox("Jenis", ["Personil", "Sarana Kantor", "Alat"])
            nm = st.text_input("Nama Item")
            cond = st.text_input("Kondisi/Jabatan")
            if st.form_submit_button("Simpan SDM"): st.success(app.tambah_sdm_sarana(jns, nm, cond, "-"))
        st.data_editor(app.get_table_data('data_sdm_sarana'), key='ed_sdm', num_rows="dynamic")

# --- PETA GIS ---
elif menu == "Peta Digital (GIS)":
    st.header("🗺️ Peta Jaringan Irigasi")
    up = st.file_uploader("Upload File KML/KMZ", type=["kml"])
    if up:
        m, msg = parse_kml_to_map(up)
        st.success(msg)
        st_folium(m, width=1000, height=500)
    else:
        st_folium(folium.Map([-4.5, 103.0], zoom_start=9), width=1000, height=500)

# --- ANALISA & EXPORT ---
elif menu == "Analisa & Export":
    st.header("Analisa & Laporan")
    df = app.get_data()
    
    st.subheader("1. Prioritas Penanganan")
    if not df.empty:
        rb = df[df['nilai_kinerja'] < 60]
        if not rb.empty:
            st.error(f"Ditemukan {len(rb)} aset Rusak Berat:")
            st.dataframe(rb)
        else: st.success("Semua aset aman.")
    
    st.divider()
    st.subheader("2. Download Laporan")
    if st.button("📄 Generate Excel (Lengkap)"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Aset Fisik', index=False)
            app.get_table_data('data_tanam').to_excel(writer, sheet_name='Data Tanam', index=False)
            app.get_table_data('data_p3a').to_excel(writer, sheet_name='Kelembagaan P3A', index=False)
            app.get_table_data('data_sdm_sarana').to_excel(writer, sheet_name='SDM & Sarana', index=False)
        st.download_button("📥 Download File Excel", buffer, "Laporan_SIKI_Lengkap.xlsx")
