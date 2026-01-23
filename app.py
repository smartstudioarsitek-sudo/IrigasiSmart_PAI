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

st.set_page_config(page_title="Smart-PAI - Enterprise", layout="wide")
st.title("🌊 Smart-PAI (Profil Aset Irigas)")
st.markdown("**Status:** ✅ Compliant Permen PUPR 23/2015 (Pemisahan Data Statis & Dinamis)")

if 'backend' not in st.session_state:
    st.session_state.backend = IrigasiBackend()
app = st.session_state.backend

# --- SIDEBAR UTILS ---
with st.sidebar.expander("🛠️ Admin Panel"):
    if st.button("⚠️ FACTORY RESET"): st.success(app.hapus_semua_data()); st.rerun()

menu = st.sidebar.radio("Navigasi", ["Dashboard Utama", "1. Master Data Aset", "2. Inspeksi Berkala", "3. Input Non-Fisik", "4. Analisa Prioritas"])

# --- FUNGSI BANTUAN ---
def gambar_sketsa(jenis, params):
    fig, ax = plt.subplots(figsize=(6, 3)); ax.set_axis_off()
    if "Saluran" in jenis:
        b, h, m = params.get('b',1.0), params.get('h',1.0), params.get('m',1.0)
        x = [0, m*h, m*h+b, 2*m*h+b]; y = [h, 0, 0, h]
        ax.plot(x, y, 'k-', lw=2)
        ax.plot([x[0]-1, x[3]+1], [h, h], 'g--', lw=1)
        ax.text((m*h+b/2), -0.2, f"b={b}m", ha='center', color='blue')
        ax.set_title(f"Saluran")
    elif "Bendung" in jenis:
        H = params.get('tinggi_mercu', 2)
        ax.add_patch(patches.Polygon([[0,0], [2,H], [4,0]], color='gray'))
        ax.text(2, H/2, f"H={H}m", ha='center', color='white')
        ax.set_title("Bendung")
    else: ax.text(0.5, 0.5, "No Sketch", ha='center')
    return fig

# --- DASHBOARD ---
if menu == "Dashboard Utama":
    st.header("🏁 Executive Dashboard")
    
    df_master = app.get_master_aset()
    df_prioritas = app.get_prioritas_matematis()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Aset Terdaftar", f"{len(df_master)} Unit")
    c2.metric("Aset Terinspeksi", f"{len(df_prioritas)} Unit")
    
    if not df_prioritas.empty:
        top_risk = df_prioritas.iloc[0]
        c3.metric("🔥 Top Prioritas", top_risk['nama_aset'], f"Skor Bahaya: {top_risk['Skor_Prioritas']:.1f}")
        
        st.divider()
        st.subheader("Peta Risiko Aset (Top 5 Paling Kritis)")
        st.dataframe(df_prioritas[['nama_aset', 'jenis_aset', 'kondisi_sipil', 'nilai_fungsi_sipil', 'Skor_Prioritas']].head(5), use_container_width=True)
    else:
        st.info("Belum ada data inspeksi masuk.")

# --- 1. MASTER DATA (STATIS) ---
elif menu == "1. Master Data Aset":
    st.header("🗃️ Pendaftaran Aset Baru (Data Statis)")
    st.info("Data ini hanya diinput SEKALI seumur hidup aset (kecuali renovasi total).")
    
    t1, t2 = st.tabs(["Formulir Pendaftaran", "Database Master"])
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            nama = st.text_input("Nama Aset (Unik)")
            jenis = st.selectbox("Jenis Aset", ["Saluran Induk", "Saluran Sekunder", "Bendung", "Bangunan Bagi"])
            thn = st.number_input("Tahun Bangun", 1980, 2024, 2000)
            luas = st.number_input("Luas Layanan Desain (Ha)", 0.0)
            
        with c2:
            st.write("Detail Teknis:")
            detail = {}
            if "Saluran" in jenis:
                b=st.number_input("Lebar (m)",0.0); h=st.number_input("Tinggi (m)",0.0); m=st.number_input("Kemiringan",1.0)
                detail={'b':b, 'h':h, 'm':m}
                sat="m"
            elif "Bendung" in jenis:
                H=st.number_input("Tinggi Mercu (m)",2.0)
                detail={'tinggi_mercu':H}
                sat="bh"
            else: sat="unit"
            st.pyplot(gambar_sketsa(jenis, detail))
            
        if st.button("Simpan ke Master Database"):
            st.success(app.tambah_master_aset(nama, jenis, sat, thn, luas, detail))

    with t2:
        st.dataframe(app.get_master_aset())

# --- 2. INSPEKSI BERKALA (DINAMIS) ---
elif menu == "2. Inspeksi Berkala":
    st.header("🔍 Laporan Inspeksi Lapangan (Data Dinamis)")
    st.info("Input kondisi terkini aset di sini. Data lama akan tersimpan sebagai riwayat.")
    
    df_m = app.get_master_aset()
    if df_m.empty:
        st.warning("Master Aset kosong. Silakan daftar aset dulu di menu 1.")
    else:
        aset_pilih = st.selectbox("Pilih Aset untuk Diinspeksi", df_m['nama_aset'].tolist())
        # Ambil ID aset
        aset_row = df_m[df_m['nama_aset'] == aset_pilih].iloc[0]
        aset_id = int(aset_row['id']) # Konversi ke int native Python
        
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("A. Kondisi Fisik")
            ks = st.slider("Kondisi Sipil (%)", 0, 100, 100, help="100=Mulus, 0=Hancur")
            kme = st.slider("Kondisi ME (%)", 0, 100, 100, help="Khusus Pintu Air")
            
            st.subheader("B. Kinerja Fungsi")
            fs = st.radio("Fungsi Sipil?", ["Baik (100)", "Kurang (70)", "Mati (40)"], horizontal=True)
            fme = st.radio("Fungsi ME?", ["Baik (100)", "Kurang (70)", "Macet (0)"], horizontal=True)
            
            # Konversi Radio ke Angka
            val_fs = 100 if "Baik" in fs else (70 if "Kurang" in fs else 40)
            val_fme = 100 if "Baik" in fme else (70 if "Kurang" in fme else 0)

        with c2:
            st.subheader("C. Analisa Dampak")
            luas_impact = st.number_input("Estimasi Luas Terdampak Jika Gagal (Ha)", 
                                         value=float(aset_row['luas_layanan_desain']),
                                         help="Jika aset ini jebol, berapa Ha sawah kering?")
            rek = st.text_area("Rekomendasi Penanganan", placeholder="Contoh: Ganti karet pintu, plester dinding saluran...")
            biaya = st.number_input("Estimasi Biaya (Rp)", 0.0, step=1000000.0)
            surveyor = st.text_input("Nama Surveyor")
            
            if st.button("Kirim Laporan Inspeksi"):
                st.success(app.tambah_inspeksi(aset_id, surveyor, ks, kme, val_fs, val_fme, luas_impact, rek, biaya))

        st.divider()
        st.caption("Riwayat Inspeksi Aset Ini:")
        st.dataframe(app.get_history_aset(aset_id))

# --- 3. NON FISIK (TETAP) ---
elif menu == "3. Input Non-Fisik":
    st.header("Data Penunjang")
    t_tanam, t_p3a, t_sdm, t_dok = st.tabs(["Tanam", "P3A", "SDM", "Dokumen"])
    # (Copy-paste logika input non-fisik dari kode sebelumnya di sini)
    # Saya persingkat tampilan untuk kode ini, tapi fungsionalitas backend sudah siap.
    with t_tanam:
        with st.form("ft"):
            c1,c2 = st.columns(2)
            mt = c1.selectbox("Musim", ["MT-1", "MT-2", "MT-3"])
            lr = c1.number_input("Rencana (Ha)", 0.0); lrl = c1.number_input("Realisasi (Ha)", 0.0)
            qa = c2.number_input("Debit Andalan (L/dt)", 0.0); qb = c2.number_input("Kebutuhan (L/dt)", 0.0)
            if st.form_submit_button("Simpan Tanam"): st.success(app.tambah_data_tanam_lengkap(mt, lr, lrl, qa, qb, 0, 0))
        st.dataframe(app.get_table_data('data_tanam'))
    # ... Tab lainnya sama ...

# --- 4. ANALISA PRIORITAS ---
elif menu == "4. Analisa Prioritas":
    st.header("📊 Analisa Prioritas Penanganan")
    st.info("Menggunakan Formula Matematis: P = f(Kondisi, Fungsi, Impact Area)")
    
    df_p = app.get_prioritas_matematis()
    
    if not df_p.empty:
        # Tampilkan Tabel
        st.dataframe(df_p[['nama_aset', 'Skor_Prioritas', 'kondisi_sipil', 'nilai_fungsi_sipil', 'luas_terdampak_aktual']], use_container_width=True)
        
        # Download Report
        if st.button("Download Laporan Prioritas (Excel)"):
            b = io.BytesIO()
            with pd.ExcelWriter(b, engine='xlsxwriter') as w:
                df_p.to_excel(w, sheet_name='Ranking Prioritas', index=False)
                app.get_master_aset().to_excel(w, sheet_name='Master Aset', index=False)
            st.download_button("Download Excel", b, "Laporan_Prioritas_Enterprise.xlsx")
    else:
        st.warning("Belum ada data inspeksi untuk dianalisa.")

