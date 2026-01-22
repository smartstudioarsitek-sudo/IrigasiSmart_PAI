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

st.set_page_config(page_title="IKSI - Standar Permen 23/2015", layout="wide")
st.title("🌊 IKSI (Sistem Informasi Kinerja Irigasi)")
st.caption("✅ Compliant with Permen PUPR 23/2015 | Feeder System for EPAKSI")

if 'backend' not in st.session_state:
    st.session_state.backend = IrigasiBackend()
app = st.session_state.backend

# --- FUNGSI BANTUAN (TETAP) ---
def parse_kml_to_map(kml_file):
    m = folium.Map([-4.5, 103.0], zoom_start=12)
    try:
        root = ET.fromstring(kml_file.getvalue().decode("utf-8"))
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        count = 0
        for placemark in root.findall('.//kml:Placemark', ns):
            name = placemark.find('kml:name', ns).text or "Aset"
            for geom in ['Polygon', 'LineString', 'Point']:
                obj = placemark.find(f'.//kml:{geom}', ns)
                if obj:
                    coords = []
                    for c in obj.find('.//kml:coordinates', ns).text.strip().split():
                        lon, lat, *_ = map(float, c.split(','))
                        coords.append([lat, lon])
                    if geom=='Polygon': folium.Polygon(coords, color="blue", fill=True, popup=name).add_to(m)
                    elif geom=='LineString': folium.PolyLine(coords, color="red", weight=4, popup=name).add_to(m)
                    elif geom=='Point': folium.Marker(coords[0], popup=name).add_to(m)
                    count += 1
        return m, f"Loaded {count} assets."
    except: return m, "Error reading KML"

def gambar_sketsa(jenis, params):
    fig, ax = plt.subplots(figsize=(6, 3)); ax.set_axis_off()
    if "Saluran" in jenis:
        b, h, m = params.get('b',1.0), params.get('h',1.0), params.get('m',1.0)
        x = [0, m*h, m*h+b, 2*m*h+b]; y = [h, 0, 0, h]
        ax.plot(x, y, 'k-', lw=2)
        ax.plot([x[0]-1, x[3]+1], [h, h], 'g--', lw=1)
        ax.text((m*h+b/2), -0.2, f"b={b}m", ha='center', color='blue')
        ax.set_title(f"Saluran ({params.get('tipe_lining','Tanah')})")
    elif "Bendung" in jenis:
        H = params.get('tinggi_mercu', 2)
        ax.add_patch(patches.Polygon([[0,0], [2,H], [4,0]], color='gray'))
        ax.text(2, H/2, f"H={H}m", ha='center', color='white')
        ax.set_title("Bendung")
    else: ax.text(0.5, 0.5, "No Sketch", ha='center')
    return fig

# --- SIDEBAR ---
with st.sidebar.expander("🛠️ Teknisi"):
    if st.button("⚠️ RESET DATA"): st.success(app.hapus_semua_data()); st.rerun()
    st.download_button("⬇️ Backup JSON", app.export_ke_json(), "backup.json")
    up = st.file_uploader("⬆️ Restore JSON")
    if up and st.button("Restore"): st.success(app.import_dari_json(up)); st.rerun()

menu = st.sidebar.radio("Navigasi", ["Dashboard IKSI", "Input Aset Fisik", "Input Non-Fisik", "Peta GIS", "Laporan"])

# --- DASHBOARD IKSI LENGKAP ---
if menu == "Dashboard IKSI":
    st.header("🏁 Dashboard Kinerja Sistem Irigasi (IKSI)")
    
    # Hitung Skor IKSI Real-time
    data_iksi = app.hitung_skor_iksi_lengkap()
    total = data_iksi['Total IKSI']
    
    # Tentukan Warna Kinerja
    warna = "red"
    label = "BURUK (Perlu Perhatian Khusus)"
    if total >= 80: warna, label = "green", "BAIK SEKALI"
    elif total >= 70: warna, label = "green", "BAIK"
    elif total >= 55: warna, label = "orange", "KURANG / SEDANG"
    
    col_utama, col_detail = st.columns([1, 2])
    
    with col_utama:
        st.metric("SKOR IKSI FINAL", f"{total}", delta=label)
        st.progress(total/100)
        st.info("Nilai ini adalah gabungan dari 6 Aspek sesuai Permen 23/2015.")
        
    with col_detail:
        st.subheader("Rincian 6 Pilar IKSI")
        rincian = data_iksi['Rincian']
        # Tampilkan Progress Bar Tiap Aspek
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Prasarana Fisik** (Bobot 45%): {rincian['Prasarana Fisik (45%)']}")
            st.progress(rincian['Prasarana Fisik (45%)']/100)
            st.write(f"**Produktivitas Tanam** (15%): {rincian['Produktivitas Tanam (15%)']}")
            st.progress(rincian['Produktivitas Tanam (15%)']/100)
            st.write(f"**Sarana Penunjang** (10%): {rincian['Sarana Penunjang (10%)']}")
            st.progress(rincian['Sarana Penunjang (10%)']/100)
        with c2:
            st.write(f"**Organisasi Personalia** (15%): {rincian['Organisasi Personalia (15%)']}")
            st.progress(rincian['Organisasi Personalia (15%)']/100)
            st.write(f"**Dokumentasi** (5%): {rincian['Dokumentasi (5%)']}")
            st.progress(rincian['Dokumentasi (5%)']/100)
            st.write(f"**Kelembagaan P3A** (10%): {rincian['Kelembagaan P3A (10%)']}")
            st.progress(rincian['Kelembagaan P3A (10%)']/100)

# --- INPUT ASET FISIK (DENGAN LUAS LAYANAN) ---
elif menu == "Input Aset Fisik":
    st.header("📝 Input Prasarana Fisik")
    t1, t2 = st.tabs(["Formulir", "Tabel Data"])
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            jenis = st.selectbox("Jenis", ["Saluran (Primer/Sekunder)", "Bendung", "Bangunan Bagi", "Lainnya"])
            nama = st.text_input("Nama Aset")
            # --- UPDATE: KOLOM LUAS LAYANAN (KRITIKAL UNTUK REGULASI) ---
            luas_layanan = st.number_input("Luas Layanan (Ha)", min_value=0.0, help="Penting untuk pembobotan skor kinerja!")
            # ------------------------------------------------------------
            peta = st.file_uploader("Upload KMZ", type=['kml','kmz'])
            
            detail = {}
            if "Saluran" in jenis:
                b = st.number_input("Lebar (b)", 0.0, step=0.05)
                h = st.number_input("Tinggi (h)", 0.0, step=0.05)
                m = st.number_input("Miring (m)", 0.0, step=0.05)
                detail = {"b":b, "h":h, "m":m, "tipe_lining":st.selectbox("Lining", ["Tanah","Beton"])}
                sat = "m"
            elif "Bendung" in jenis:
                H = st.number_input("Tinggi Mercu", 0.0, step=0.05)
                detail = {"tinggi_mercu":H}
                sat = "bh"
            else: sat = "unit"

        with c2:
            st.pyplot(gambar_sketsa(jenis, detail))
            st.divider()
            cb = st.number_input("Volume Baik", 0.0)
            crr = st.number_input("Volume RR", 0.0)
            crb = st.number_input("Volume RB", 0.0)
            
            if st.button("Simpan Data"):
                msg = app.tambah_data_kompleks(nama, jenis, sat, cb, crr, crb, luas_layanan, detail, peta)
                st.success(msg)

    with t2:
        df = app.get_data()
        ed = st.data_editor(df, hide_index=True, use_container_width=True)
        if st.button("Update Tabel"): app.update_data(ed); st.rerun()

# --- INPUT NON FISIK ---
elif menu == "Input Non-Fisik":
    st.header("📋 Data Penunjang (5 Pilar Lainnya)")
    t_tanam, t_p3a, t_sdm = st.tabs(["Tanam", "P3A", "SDM"])
    
    with t_tanam:
        with st.form("ft"):
            c1,c2 = st.columns(2)
            musim = c1.selectbox("Musim", ["MT-1", "MT-2", "MT-3"])
            luas = c2.number_input("Rencana (Ha)", 0.0)
            real = c2.number_input("Realisasi (Ha)", 0.0)
            padi = c1.number_input("Prod Padi (Ton/Ha)", 0.0)
            pala = c1.number_input("Prod Palawija (Ton/Ha)", 0.0)
            if st.form_submit_button("Simpan"): st.success(app.tambah_data_tanam(musim, luas, real, padi, pala))
        st.dataframe(app.get_table_data('data_tanam'))

    with t_p3a:
        with st.form("fp"):
            nm = st.text_input("Nama P3A"); ds = st.text_input("Desa")
            stt = st.selectbox("Badan Hukum", ["Sudah", "Belum"])
            akt = st.selectbox("Keaktifan", ["Aktif", "Sedang", "Kurang"])
            ang = st.number_input("Anggota", 0)
            if st.form_submit_button("Simpan"): st.success(app.tambah_data_p3a(nm, ds, stt, akt, ang))
        st.dataframe(app.get_table_data('data_p3a'))

    with t_sdm:
        with st.form("fs"):
            jns = st.selectbox("Jenis", ["Personil", "Sarana Kantor", "Alat"])
            nm = st.text_input("Nama Item"); cond = st.text_input("Kondisi/Jabatan")
            if st.form_submit_button("Simpan"): st.success(app.tambah_sdm_sarana(jns, nm, cond, "-"))
        st.dataframe(app.get_table_data('data_sdm_sarana'))

# --- PETA GIS ---
elif menu == "Peta GIS":
    st.header("🗺️ Peta Jaringan")
    up = st.file_uploader("Upload KMZ", type=["kml"])
    if up: 
        m, msg = parse_kml_to_map(up)
        st.success(msg)
        st_folium(m, width=1000)
    else: st_folium(folium.Map([-4.5, 103], zoom_start=10), width=1000)

# --- LAPORAN ---
elif menu == "Laporan":
    st.header("📄 Export Laporan")
    if st.button("Download Excel (Format Raw)"):
        b = io.BytesIO()
        with pd.ExcelWriter(b, engine='xlsxwriter') as w:
            app.get_data().to_excel(w, sheet_name='Fisik', index=False)
            app.get_table_data('data_tanam').to_excel(w, sheet_name='Tanam', index=False)
            app.get_table_data('data_p3a').to_excel(w, sheet_name='P3A', index=False)
            app.get_table_data('data_sdm_sarana').to_excel(w, sheet_name='SDM', index=False)
        st.download_button("Download", b, "Laporan_SIKI.xlsx")

