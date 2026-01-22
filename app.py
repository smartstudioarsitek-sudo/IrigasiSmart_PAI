import streamlit as st
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from modules.backend import IrigasiBackend

# Config
st.set_page_config(page_title="SIKI - Sistem Irigasi", layout="wide")
st.title("🌊 Sistem Informasi Kinerja Irigasi (SIKI)")

if 'backend' not in st.session_state:
    st.session_state.backend = IrigasiBackend()
app = st.session_state.backend

# --- FUNGSI GAMBAR (VISUALISASI) ---
def gambar_sketsa(jenis, params):
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.set_axis_off()
    if jenis == "Saluran (Primer/Sekunder/Tersier)":
        b, h, m = params.get('b', 1.0), params.get('h', 1.0), params.get('m', 1.0)
        x = [0, m*h, m*h + b, 2*m*h + b]
        y = [h, 0, 0, h]
        ax.plot(x, y, 'k-', linewidth=2)
        ax.plot([x[0]-1, x[3]+1], [h, h], 'g--', linewidth=1, label="Muka Tanah")
        ax.text((m*h + b/2), -0.2, f"b = {b} m", ha='center', color='blue')
        ax.set_title(f"Sketsa Penampang ({params.get('tipe_lining','Tanah')})")
    elif jenis == "Bendung":
        H = params.get('tinggi_mercu', 2)
        polygon = patches.Polygon([[0, 0], [2, H], [4, 0]], closed=True, edgecolor='black', facecolor='gray')
        ax.add_patch(polygon)
        ax.text(2, H/2, f"H = {H} m", ha='center', color='white')
        ax.set_title("Sketsa Bendung")
    else:
        ax.text(0.5, 0.5, "Visualisasi belum tersedia", ha='center')
    return fig

# --- MENU NAVIGASI ---
menu = st.sidebar.radio("Menu Navigasi", [
    "Dashboard", 
    "Input Aset Fisik", 
    "Input Data Non-Fisik", 
    "Peta Digital (GIS)", 
    "Analisa Kinerja"
])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.header("Ringkasan Daerah Irigasi")
    df = app.get_data()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Aset Fisik", f"{len(df)} Unit")
    c2.metric("Rata-rata Kinerja Fisik", f"{df['nilai_kinerja'].mean() if not df.empty else 0:.1f}%")
    
    # Ringkasan Non Fisik
    df_p3a = app.get_table_data('data_p3a')
    c3.metric("Jumlah P3A Terdaftar", f"{len(df_p3a)} Kelompok")
    
    st.divider()
    if not df.empty:
        st.subheader("Grafik Kondisi Fisik")
        st.bar_chart(df['nilai_kinerja'])

# --- INPUT ASET FISIK (MENU LAMA) ---
elif menu == "Input Aset Fisik":
    st.header("📝 Input Data Prasarana Fisik")
    t1, t2 = st.tabs(["Formulir Detail", "Data Tabel"])
    
    with t1:
        c_kiri, c_kanan = st.columns([1, 1])
        with c_kiri:
            jenis = st.selectbox("Jenis Bangunan:", ["Saluran (Primer/Sekunder/Tersier)", "Bendung", "Bangunan Bagi/Sadap", "Lainnya"])
            nama = st.text_input("Nama Aset / Ruas")
            
            detail_input = {}
            if "Saluran" in jenis:
                b = st.number_input("Lebar Dasar (b)", 1.0)
                h = st.number_input("Tinggi Jagaan (h)", 1.0)
                m = st.number_input("Kemiringan (m)", 1.0)
                detail_input = {"b": b, "h": h, "m": m, "tipe_lining": st.selectbox("Lining", ["Tanah", "Beton"])}
                satuan = "m"
            elif "Bendung" in jenis:
                H = st.number_input("Tinggi Mercu (m)", 2.0)
                detail_input = {"tinggi_mercu": H, "tipe_mercu": st.selectbox("Tipe", ["Bulat", "Ogee"])}
                satuan = "bh"
            else:
                satuan = "unit"

        with c_kanan:
            if detail_input:
                st.pyplot(gambar_sketsa(jenis, detail_input))
            st.divider()
            cb = st.number_input("Vol Baik", min_value=0.0)
            crr = st.number_input("Vol Rusak Ringan", min_value=0.0)
            crb = st.number_input("Vol Rusak Berat", min_value=0.0)
            
            if st.button("Simpan Data Fisik"):
                st.success(app.tambah_data_kompleks(nama, jenis, satuan, cb, crr, crb, detail_input))

    with t2:
        df = app.get_data()
        ed = st.data_editor(df, hide_index=True, num_rows="dynamic", use_container_width=True)
        if st.button("Update Tabel Fisik"):
            app.update_data(ed)
            st.rerun()

# --- INPUT DATA NON-FISIK (MENU BARU!) ---
elif menu == "Input Data Non-Fisik":
    st.header("📋 Data Penunjang (Non-Fisik)")
    st.info("Sesuai Permen PUPR 23/2015: Produktivitas, Kelembagaan, dan SDM.")
    
    tab_tanam, tab_p3a, tab_sdm = st.tabs(["🌾 Produktivitas Tanam", "👥 Kelembagaan P3A", "🏢 SDM & Sarana"])
    
    # --- TAB 1: TANAM ---
    with tab_tanam:
        with st.form("form_tanam"):
            c1, c2 = st.columns(2)
            musim = c1.selectbox("Musim Tanam", ["MT-1 (Rendeng)", "MT-2 (Gadu I)", "MT-3 (Gadu II)"])
            luas = c2.number_input("Rencana Luas Tanam (Ha)", min_value=0.0)
            realisasi = c2.number_input("Realisasi Luas Tanam (Ha)", min_value=0.0)
            padi = c1.number_input("Produktivitas Padi (Ton/Ha)", min_value=0.0)
            palawija = c1.number_input("Produktivitas Palawija (Ton/Ha)", min_value=0.0)
            if st.form_submit_button("Simpan Data Tanam"):
                st.success(app.tambah_data_tanam(musim, luas, realisasi, padi, palawija))
        
        st.write("Riwayat Data Tanam:")
        df_tanam = app.get_table_data('data_tanam')
        st.data_editor(df_tanam, num_rows="dynamic", key='editor_tanam')

    # --- TAB 2: P3A ---
    with tab_p3a:
        with st.form("form_p3a"):
            c1, c2 = st.columns(2)
            nama_p3a = c1.text_input("Nama P3A / GP3A")
            desa = c1.text_input("Wilayah Desa")
            status = c2.selectbox("Status Badan Hukum", ["Sudah Berbadan Hukum", "Belum", "Dalam Proses"])
            aktif = c2.selectbox("Keaktifan", ["Aktif", "Sedang", "Kurang Aktif/Macet"])
            anggota = c1.number_input("Jumlah Anggota (Orang)", min_value=0, step=1)
            if st.form_submit_button("Simpan Data P3A"):
                st.success(app.tambah_data_p3a(nama_p3a, desa, status, aktif, anggota))
        
        st.write("Daftar P3A:")
        df_p3a = app.get_table_data('data_p3a')
        st.data_editor(df_p3a, num_rows="dynamic", key='editor_p3a')

    # --- TAB 3: SDM & SARANA ---
    with tab_sdm:
        st.write("Data Personil (Juru/Pengamat) dan Sarana Kantor")
        with st.form("form_sdm"):
            jenis = st.selectbox("Jenis Data", ["Personil/SDM", "Sarana Kantor", "Alat Transportasi", "Alat Komunikasi"])
            nama_item = st.text_input("Nama Personil / Nama Barang")
            kondisi = st.text_input("Jabatan / Kondisi Barang", placeholder="Contoh: Juru Air atau Rusak Ringan")
            ket = st.text_input("Keterangan Tambahan")
            if st.form_submit_button("Simpan Data SDM/Sarana"):
                st.success(app.tambah_sdm_sarana(jenis, nama_item, kondisi, ket))
        
        st.write("Data SDM & Sarana:")
        df_sdm = app.get_table_data('data_sdm_sarana')
        st.data_editor(df_sdm, num_rows="dynamic", key='editor_sdm')

# --- PETA DIGITAL ---
elif menu == "Peta Digital (GIS)":
    st.header("Peta Wilayah")
    st.info("Fitur visualisasi peta (Upload KML di menu Input Aset Fisik).")
    # (Kode peta sederhana, bisa dikembangkan nanti)

# --- ANALISA KINERJA ---
elif menu == "Analisa Kinerja":
    st.header("Analisa Kinerja Sistem")
    st.write("Analisa gabungan Fisik & Non-Fisik akan muncul di sini setelah data lengkap.")
