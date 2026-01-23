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

st.set_page_config(page_title="SIKI - Audit Ready", layout="wide")
st.title("🌊 SIKI (Sistem Informasi Kinerja Irigasi)")
st.markdown("✅ **Status:** Compliant Permen PUPR 23/2015 (Kondisi vs Fungsi Terpisah)")

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
        return m, f"Loaded {count} items."
    except: return m, "Error KML"

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
with st.sidebar.expander("🛠️ Maintenance"):
    if st.button("⚠️ RESET DATA"): st.success(app.hapus_semua_data()); st.rerun()
    st.download_button("⬇️ Backup JSON", app.export_ke_json(), "backup.json")
    up = st.file_uploader("⬆️ Restore JSON")
    if up and st.button("Restore"): st.success(app.import_dari_json(up)); st.rerun()

menu = st.sidebar.radio("Navigasi", ["Dashboard", "Input Aset (Kondisi & Fungsi)", "Input Non-Fisik", "Peta GIS", "Laporan & Prioritas"])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.header("🏁 Dashboard Kinerja")
    data = app.hitung_skor_iksi_audit()
    st.metric("IKSI TOTAL", data['Total IKSI'])
    st.info("Nilai ini sudah memperhitungkan bobot area dan faktor hidrologi.")

# --- INPUT ASET (REVISI BESAR: KONDISI vs FUNGSI) ---
elif menu == "Input Aset (Kondisi & Fungsi)":
    st.header("1. Inventarisasi Aset (Fisik & Fungsional)")
    st.warning("⚠️ Permen PUPR 23/2015 Wajib memisahkan Kondisi Fisik & Fungsi.")
    
    t1, t2 = st.tabs(["Formulir", "Tabel Data"])
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            jenis = st.selectbox("Jenis", ["Saluran (Primer/Sekunder)", "Bendung", "Bangunan Bagi", "Lainnya"])
            nama = st.text_input("Nama Aset")
            luas = st.number_input("Luas Layanan (Ha)", 0.0, help="Penting untuk prioritas!")
            peta = st.file_uploader("Upload KMZ", type=['kmz','kml'])
            
            # Form Detail Teknis
            detail = {}
            if "Saluran" in jenis:
                b=st.number_input("b",0.0,step=0.1); h=st.number_input("h",0.0,step=0.1); m=st.number_input("m",0.0,step=0.1)
                detail={'b':b,'h':h,'m':m,'tipe_lining':st.selectbox("Lining",["Tanah","Beton"])}
                sat="m"
            elif "Bendung" in jenis:
                H=st.number_input("H Mercu",2.0,step=0.1)
                detail={'tinggi_mercu':H}
                sat="bh"
            else: sat="unit"

        with c2:
            st.pyplot(gambar_sketsa(jenis, detail))
            st.divider()
            
            st.subheader("A. Kondisi Fisik (Kerusakan Material)")
            col_f1, col_f2, col_f3 = st.columns(3)
            cb = col_f1.number_input("Baik", 0.0)
            crr = col_f2.number_input("R.Ringan", 0.0)
            crb = col_f3.number_input("R.Berat", 0.0)
            
            st.subheader("B. Kinerja Fungsi (Hidrolis)")
            fungsi_opt = st.radio("Bagaimana fungsi aset ini?", 
                ["Berfungsi Baik (>90%)", "Kurang Berfungsi (60-90%)", "Tidak Berfungsi (<60%)"],
                help="Apakah air bisa mengalir? Apakah pintu bisa dibuka?")
            
            # Konversi Radio ke Angka
            skor_fungsi = 100
            if "Kurang" in fungsi_opt: skor_fungsi = 70
            elif "Tidak" in fungsi_opt: skor_fungsi = 40
            
            if st.button("Simpan Data Lengkap"):
                msg = app.tambah_data_kompleks(nama, jenis, sat, cb, crr, crb, luas, skor_fungsi, detail, peta)
                st.success(msg)

    with t2:
        df = app.get_data()
        st.dataframe(df, use_container_width=True)
        if st.button("Refresh Tabel"): st.rerun()

# --- INPUT NON FISIK (TETAP) ---
elif menu == "Input Non-Fisik":
    st.header("Data Penunjang")
    t_tanam, t_p3a, t_sdm, t_dok = st.tabs(["Tanam", "P3A", "SDM", "Dokumen"])
    
    with t_tanam:
        with st.form("ft"):
            c1,c2 = st.columns(2)
            mt = c1.selectbox("Musim", ["MT-1", "MT-2", "MT-3"])
            lr = c1.number_input("Rencana (Ha)", 0.0)
            lrl = c1.number_input("Realisasi (Ha)", 0.0)
            q_and = c2.number_input("Debit Andalan (L/dt)", 0.0)
            q_but = c2.number_input("Kebutuhan Air (L/dt)", 0.0)
            padi = c1.number_input("Padi (Ton)", 0.0)
            pala = c1.number_input("Palawija (Ton)", 0.0)
            if st.form_submit_button("Simpan"): st.success(app.tambah_data_tanam_lengkap(mt, lr, lrl, q_and, q_but, padi, pala))
        st.dataframe(app.get_table_data('data_tanam'))

    with t_p3a:
        with st.form("p3a"):
            nm=st.text_input("Nama"); stt=st.selectbox("Badan Hukum", ["Sudah", "Belum"]); akt=st.selectbox("Keaktifan", ["Aktif", "Sedang", "Kurang"])
            if st.form_submit_button("Simpan"): st.success(app.tambah_data_p3a(nm, "-", stt, akt, 0))
        st.dataframe(app.get_table_data('data_p3a'))
        
    with t_sdm:
        with st.form("sdm"):
            jns=st.selectbox("Jenis", ["Personil", "Sarana"]); nm=st.text_input("Nama"); cond=st.text_input("Kondisi")
            if st.form_submit_button("Simpan"): st.success(app.tambah_sdm_sarana(jns, nm, cond, "-"))
        st.dataframe(app.get_table_data('data_sdm_sarana'))

    with t_dok:
        st.write("Checklist Dokumen")
        dok_list = ["Peta DI", "Skema Jaringan", "Buku Data", "Manual OP"]
        exist = app.get_table_data('data_dokumentasi')
        exist_map = dict(zip(exist['jenis_dokumen'], exist['ada'])) if not exist.empty else {}
        new_stat = {}
        for d in dok_list:
            new_stat[d] = st.checkbox(d, value=bool(exist_map.get(d,0)))
        if st.button("Update Dokumen"): st.success(app.update_dokumentasi(new_stat))

# --- PETA GIS ---
elif menu == "Peta GIS":
    st.header("🗺️ Peta")
    up = st.file_uploader("KMZ", type=["kml"])
    if up: 
        m, msg = parse_kml_to_map(up)
        st_folium(m, width=1000)
    else: st_folium(folium.Map([-4.5, 103], zoom_start=10), width=1000)

# --- LAPORAN & PRIORITAS (MENU BARU) ---
elif menu == "Laporan & Prioritas":
    st.header("Analisa & Laporan Akhir")
    
    st.subheader("1. Matriks Prioritas Penanganan")
    st.info("Dihitung berdasarkan Fungsi (Hidrolis) dan Kondisi (Fisik).")
    
    df_prioritas = app.get_prioritas_penanganan()
    if not df_prioritas.empty:
        # Tampilkan kolom penting saja
        st.dataframe(df_prioritas[['nama_aset', 'jenis_aset', 'nilai_fisik', 'nilai_fungsi', 'Rekomendasi']], use_container_width=True)
    else:
        st.warning("Belum ada data aset.")
        
    st.divider()
    st.subheader("2. Export Laporan Resmi")
    if st.button("Download Excel (Format Laporan)"):
        b = io.BytesIO()
        with pd.ExcelWriter(b, engine='xlsxwriter') as w:
            # Sheet Aset (Dengan Kolom Terpisah Kondisi & Fungsi)
            app.get_data().to_excel(w, sheet_name='1. Inventarisasi Aset', index=False)
            app.get_table_data('data_tanam').to_excel(w, sheet_name='2. Data Tanam', index=False)
            if not df_prioritas.empty:
                df_prioritas.to_excel(w, sheet_name='3. Prioritas Penanganan', index=False)
        st.download_button("Download Excel", b, "Laporan_SIKI_Compliance.xlsx")
