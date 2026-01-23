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

st.set_page_config(page_title="SIKI - Compliant Version", layout="wide")
st.title("🌊 SIKI (Sistem Informasi Kinerja Irigasi)")
st.markdown("✅ **Status Audit:** Compliant Permen PUPR 23/2015 & 12/2015")

if 'backend' not in st.session_state:
    st.session_state.backend = IrigasiBackend()
app = st.session_state.backend

# --- FUNGSI PETA & GAMBAR (TETAP) ---
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

menu = st.sidebar.radio("Navigasi", ["Dashboard IKSI", "Input Aset Fisik", "Input Non-Fisik", "Peta GIS", "Laporan Resmi"])

# --- DASHBOARD AUDIT ---
if menu == "Dashboard IKSI":
    st.header("🏁 Kinerja Sistem Irigasi (Audit Mode)")
    
    data = app.hitung_skor_iksi_audit()
    total = data['Total IKSI']
    
    # Kategori Permen 12/2015
    if total >= 80: lbl, warna = "BAIK SEKALI (Layak DAK)", "green"
    elif total >= 70: lbl, warna = "BAIK", "green"
    elif total >= 55: lbl, warna = "KURANG (Perlu Rehab)", "orange"
    else: lbl, warna = "JELEK (Rusak Berat)", "red"
    
    col_main, col_break = st.columns([1,2])
    with col_main:
        st.metric("IKSI GABUNGAN", f"{total}", delta=lbl)
        st.progress(total/100)
    
    with col_break:
        st.subheader("Rincian 6 Pilar (Weighted)")
        r = data['Rincian']
        c1,c2 = st.columns(2)
        with c1:
            st.metric("1. Fisik (45%)", r['Fisik (45%)'])
            st.metric("2. Tanam (15%)", r['Tanam (15%)'])
            st.metric("3. Sarana (10%)", r['Sarana (10%)'])
        with c2:
            st.metric("4. SDM (15%)", r['SDM (15%)'])
            st.metric("5. Dokumen (5%)", r['Dokumen (5%)'])
            st.metric("6. P3A (10%)", r['P3A (10%)'])

# --- INPUT FISIK ---
elif menu == "Input Aset Fisik":
    st.header("1. Inventarisasi Aset (Bobot 45%)")
    t1, t2 = st.tabs(["Formulir", "Tabel"])
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            jenis = st.selectbox("Jenis", ["Saluran (Primer/Sekunder)", "Bendung", "Bangunan Bagi", "Lainnya"])
            nama = st.text_input("Nama Aset")
            luas = st.number_input("Luas Layanan (Ha)", 0.0, help="Wajib diisi untuk pembobotan!")
            peta = st.file_uploader("Upload KMZ", type=['kmz','kml'])
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
            cb = st.number_input("Kondisi Baik", 0.0); crr = st.number_input("Kondisi RR", 0.0); crb = st.number_input("Kondisi RB", 0.0)
            if st.button("Simpan Aset"): st.success(app.tambah_data_kompleks(nama, jenis, sat, cb, crr, crb, luas, detail, peta))
    with t2:
        ed = st.data_editor(app.get_data(), hide_index=True, use_container_width=True)
        if st.button("Update"): app.update_data(ed); st.rerun()

# --- INPUT NON FISIK (REVISI BESAR) ---
elif menu == "Input Non-Fisik":
    st.header("Data Penunjang (Bobot 55%)")
    t_tanam, t_p3a, t_sdm, t_dok = st.tabs(["2. Tanam & Air (15%)", "3. P3A (10%)", "4. SDM & Sarana (25%)", "5. Dokumentasi (5%)"])
    
    with t_tanam:
        st.info("Input Data Tanam per Musim (Wajib Isi Debit untuk Faktor K)")
        with st.form("tanam"):
            c1,c2 = st.columns(2)
            mt = c1.selectbox("Musim", ["MT-1", "MT-2", "MT-3"])
            lr = c1.number_input("Rencana Luas (Ha)", 0.0)
            lrl = c1.number_input("Realisasi Luas (Ha)", 0.0)
            q_and = c2.number_input("Debit Andalan (L/dt)", 0.0, help="Ketersediaan Air di Bendung")
            q_but = c2.number_input("Kebutuhan Air (L/dt)", 0.0, help="Kebutuhan Air di Sawah")
            padi = c1.number_input("Prod Padi (Ton/Ha)", 0.0)
            pala = c1.number_input("Prod Palawija (Ton/Ha)", 0.0)
            if st.form_submit_button("Simpan Data Tanam"):
                st.success(app.tambah_data_tanam_lengkap(mt, lr, lrl, q_and, q_but, padi, pala))
        st.dataframe(app.get_table_data('data_tanam'))

    with t_p3a:
        with st.form("p3a"):
            nm=st.text_input("Nama"); ds=st.text_input("Desa")
            stt=st.selectbox("Badan Hukum", ["Sudah", "Belum"]); akt=st.selectbox("Keaktifan", ["Aktif", "Sedang", "Kurang"])
            ang=st.number_input("Anggota",0)
            if st.form_submit_button("Simpan P3A"): st.success(app.tambah_data_p3a(nm, ds, stt, akt, ang))
        st.dataframe(app.get_table_data('data_p3a'))

    with t_sdm:
        st.write("Input Personil & Sarana Kantor")
        with st.form("sdm"):
            jns=st.selectbox("Jenis", ["Personil", "Sarana Kantor", "Alat", "Transportasi"])
            nm=st.text_input("Nama Item"); cond=st.text_input("Kondisi/Jabatan")
            if st.form_submit_button("Simpan SDM/Sarana"): st.success(app.tambah_sdm_sarana(jns, nm, cond, "-"))
        st.dataframe(app.get_table_data('data_sdm_sarana'))

    with t_dok:
        st.write("Checklist Kelengkapan Dokumen (Bobot 5%)")
        dok_list = ["Peta Daerah Irigasi", "Skema Jaringan", "Skema Bangunan", "Buku Data DI", "Manual O&P", "Gambar Purna Laksana (As-Built)"]
        
        # Ambil data existing
        df_dok = app.get_table_data('data_dokumentasi')
        existing = {}
        if not df_dok.empty:
            existing = dict(zip(df_dok['jenis_dokumen'], df_dok['ada']))
        
        new_status = {}
        for item in dok_list:
            checked = st.checkbox(item, value=bool(existing.get(item, 0)))
            new_status[item] = checked
            
        if st.button("Update Status Dokumen"):
            st.success(app.update_dokumentasi(new_status))

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
elif menu == "Laporan Resmi":
    st.header("📄 Export Laporan (Format Database)")
    if st.button("Download Excel Lengkap"):
        b = io.BytesIO()
        with pd.ExcelWriter(b, engine='xlsxwriter') as w:
            app.get_data().to_excel(w, sheet_name='1. Aset Fisik', index=False)
            app.get_table_data('data_tanam').to_excel(w, sheet_name='2. Tanam & Hidrologi', index=False)
            app.get_table_data('data_p3a').to_excel(w, sheet_name='3. Kelembagaan P3A', index=False)
            app.get_table_data('data_sdm_sarana').to_excel(w, sheet_name='4. SDM & Sarana', index=False)
            app.get_table_data('data_dokumentasi').to_excel(w, sheet_name='5. Dokumentasi', index=False)
        st.download_button("Download File Excel", b, "Laporan_IKSI_Audit.xlsx")
