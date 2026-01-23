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

st.set_page_config(page_title="SMART-PAI - Enterprise", layout="wide")
st.title("🌊 SMART-PAI (Profil Aset Irigas)")
st.markdown("✅ **Status:** Enterprise Ready (Master Data + Inspeksi Berkala)")

if 'backend' not in st.session_state:
    st.session_state.backend = IrigasiBackend()
app = st.session_state.backend

# --- SIDEBAR: ADMIN PANEL ---
st.sidebar.divider()
with st.sidebar.expander("🛠️ Admin & Backup"):
    if st.button("⚠️ RESET SEMUA DATA"): 
        app.hapus_semua_data()
        st.rerun()
    
    # Download Backup JSON
    json_data = app.export_ke_json()
    st.download_button("⬇️ Download Backup (JSON)", json_data, "backup_full.json", "application/json")
    
    # Restore Backup JSON
    up_json = st.file_uploader("⬆️ Restore Backup (JSON)", type=["json"])
    if up_json and st.button("Restore Sekarang"):
        pesan = app.import_dari_json(up_json)
        if "Berhasil" in pesan:
            st.success(pesan)
            st.rerun()
        else:
            st.error(pesan)

menu = st.sidebar.radio("Navigasi", ["Dashboard", "1. Master Aset (Statis)", "2. Inspeksi (Dinamis)", "3. Non-Fisik", "4. Laporan & Prioritas"])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.header("🏁 Executive Dashboard")
    iksi, fisik, tanam = app.hitung_iksi_lengkap()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("SKOR IKSI", f"{iksi:.2f}", delta="Target: 100")
    c2.metric("Kinerja Fisik", f"{fisik:.2f}")
    c3.metric("Produktivitas", f"{tanam:.2f}")
    
    st.divider()
    df_p = app.get_prioritas_matematis()
    if not df_p.empty:
        st.subheader("🔥 Top 5 Prioritas Penanganan (Rumus Permen PUPR)")
        st.dataframe(df_p[['nama_aset', 'Kelas_Prioritas', 'Skor_Prioritas', 'estimasi_biaya']].head(5), use_container_width=True)
    else: st.info("Belum ada data inspeksi.")

# --- 3. NON FISIK (LENGKAP) ---
elif menu == "3. Non-Fisik":
    st.header("Data Penunjang IKSI")
    st.info("Input data organisasi, teknis, dan dokumentasi sesuai Permen PUPR.")
    
    # Buat 4 Tab
    t_tanam, t_p3a, t_sdm, t_dok = st.tabs(["1. Tanam & Air", "2. P3A", "3. SDM & Sarana", "4. Dokumentasi"])
    
    # --- TAB 1: TANAM ---
    with t_tanam:
        st.write("#### Produktivitas & Ketersediaan Air")
        with st.form("ft"):
            c1,c2 = st.columns(2)
            mt = c1.selectbox("Musim Tanam", ["MT-1 (Rendeng)", "MT-2 (Gadu I)", "MT-3 (Gadu II)"])
            lr = c1.number_input("Luas Rencana (Ha)", 0.0)
            lrl = c1.number_input("Luas Realisasi (Ha)", 0.0)
            
            # Data Hidrologi untuk Faktor K
            qa = c2.number_input("Debit Andalan (L/detik)", 0.0, help="Debit tersedia di bendung")
            qb = c2.number_input("Kebutuhan Air (L/detik)", 0.0, help="Kebutuhan air di sawah")
            
            padi = c1.number_input("Prod. Padi (Ton/Ha)", 0.0)
            palawija = c1.number_input("Prod. Palawija (Ton/Ha)", 0.0)
            
            if st.form_submit_button("Simpan Data Tanam"):
                st.success(app.tambah_data_tanam_lengkap(mt, lr, lrl, qa, qb, padi, palawija))
        
        st.caption("Riwayat Data Tanam:")
        st.dataframe(app.get_table_data('data_tanam'), use_container_width=True)

    # --- TAB 2: P3A ---
    with t_p3a:
        st.write("#### Kelembagaan Petani (GP3A/IP3A)")
        with st.form("fp"):
            c1, c2 = st.columns(2)
            nm = c1.text_input("Nama P3A")
            ds = c1.text_input("Desa/Wilayah")
            stt = c2.selectbox("Status Badan Hukum", ["Sudah Berbadan Hukum", "Belum", "Proses"])
            akt = c2.selectbox("Keaktifan", ["Aktif", "Sedang", "Kurang/Macet"])
            ang = c1.number_input("Jumlah Anggota", 0, step=1)
            
            if st.form_submit_button("Simpan P3A"):
                st.success(app.tambah_data_p3a(nm, ds, stt, akt, ang))
        
        st.caption("Database P3A:")
        st.dataframe(app.get_table_data('data_p3a'), use_container_width=True)

    # --- TAB 3: SDM & SARANA ---
    with t_sdm:
        st.write("#### Personil & Peralatan Kantor")
        with st.form("fs"):
            c1, c2 = st.columns(2)
            jns = c1.selectbox("Jenis Data", ["Personil (Juru/Pengamat)", "Sarana Kantor", "Alat Transportasi", "Alat Berat"])
            nm = c1.text_input("Nama Item / Nama Personil")
            cond = c2.text_input("Kondisi / Jabatan", placeholder="Contoh: Baik / Juru Air")
            ket = c2.text_input("Keterangan")
            
            if st.form_submit_button("Simpan SDM/Sarana"):
                st.success(app.tambah_sdm_sarana(jns, nm, cond, ket))
        
        st.caption("Inventaris SDM & Sarana:")
        st.dataframe(app.get_table_data('data_sdm_sarana'), use_container_width=True)

    # --- TAB 4: DOKUMENTASI ---
    with t_dok:
        st.write("#### Checklist Kelengkapan Dokumen")
        st.info("Centang dokumen yang tersedia di kantor pengamat/UPTD.")
        
        dok_list = ["Peta Daerah Irigasi", "Skema Jaringan", "Skema Bangunan", "Buku Data DI", "Manual O&P", "Gambar Purna Laksana (As-Built)"]
        
        # Ambil data existing dari database
        df_dok = app.get_table_data('data_dokumentasi')
        existing = {}
        if not df_dok.empty:
            existing = dict(zip(df_dok['jenis_dokumen'], df_dok['ada']))
        
        # Buat Form Checklist
        new_status = {}
        col_d1, col_d2 = st.columns(2)
        
        for i, item in enumerate(dok_list):
            # Bagi dua kolom biar rapi
            col = col_d1 if i < 3 else col_d2
            is_checked = bool(existing.get(item, 0))
            new_status[item] = col.checkbox(item, value=is_checked)
            
        st.write("")
        if st.button("💾 Update Status Dokumentasi"):
            st.success(app.update_dokumentasi(new_status))

# --- 2. INSPEKSI ---
elif menu == "2. Inspeksi (Dinamis)":
    st.header("🔍 Inspeksi Berkala")
    st.warning("Penilaian dipisah: SIPIL (Struktur) vs ME (Pintu/Mesin).")
    
    m = app.get_master_aset()
    if m.empty: st.error("Master Aset Kosong!"); st.stop()
    
    aset = st.selectbox("Pilih Aset", m['nama_aset'].tolist())
    aid = int(m[m['nama_aset']==aset].iloc[0]['id'])
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Kondisi Fisik")
        ks = st.slider("Kondisi Sipil (%)", 0, 100, 100, help="Beton/Pasangan Batu")
        kme = st.slider("Kondisi ME (%)", 0, 100, 100, help="Pintu Air/Gearbox")
    with c2:
        st.subheader("Kinerja Fungsi")
        fs = st.radio("Fungsi Sipil", ["Baik (100)", "Kurang (70)", "Rusak (40)"], horizontal=True)
        fme = st.radio("Fungsi ME", ["Baik (100)", "Kurang (70)", "Macet (0)"], horizontal=True)
        nfs = 100 if "Baik" in fs else (70 if "Kurang" in fs else 40)
        nfme = 100 if "Baik" in fme else (70 if "Kurang" in fme else 0)
        
    ls_imp = st.number_input("Luas Terdampak Aktual (Ha)", 0.0, help="Berapa sawah kering jika ini rusak?")
    rek = st.text_input("Rekomendasi")
    biaya = st.number_input("Estimasi Biaya Rehab (Rp)", 0.0, step=1000000.0)
    
    if st.button("Simpan Laporan"):
        st.success(app.tambah_inspeksi(aid, "Surveyor", ks, kme, nfs, nfme, ls_imp, rek, biaya))

# --- 3. NON FISIK ---
elif menu == "3. Non-Fisik":
    st.header("Data Penunjang IKSI")
    t1, t2 = st.tabs(["Tanam & Air", "Lainnya"])
    with t1:
        c1,c2 = st.columns(2)
        mt = c1.selectbox("Musim", ["MT1","MT2"]); lr = c1.number_input("Rencana (Ha)"); lrl = c1.number_input("Realisasi (Ha)")
        qa = c2.number_input("Debit Andalan (L/dt)"); qb = c2.number_input("Kebutuhan Air (L/dt)")
        if st.button("Simpan Tanam"): st.success(app.tambah_data_tanam_lengkap(mt, lr, lrl, qa, qb, 0, 0))
        st.dataframe(app.get_table_data('data_tanam'))
    with t2:
        st.info("Fitur P3A, SDM, Dokumen tersedia di backend.")

# --- 4. LAPORAN ---
elif menu == "4. Laporan & Prioritas":
    st.header("📄 Cetak Laporan Resmi")
    st.write("Menggunakan format standar Dinas PU (Header, Tabel Prioritas, Valuasi).")
    
    if st.button("Generate Excel Blangko"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            wb = writer.book
            fmt_header = wb.add_format({'bold': True, 'align': 'center', 'bg_color': '#D9D9D9', 'border': 1})
            
            # 1. SHEET PRIORITAS
            ws1 = wb.add_worksheet('Prioritas Penanganan')
            df_p = app.get_prioritas_matematis()
            
            headers = ['Nama Aset', 'Jenis', 'Kondisi Sipil', 'Kondisi ME', 'Skor Bahaya', 'Kelas Prioritas', 'Biaya Rehab']
            for col, h in enumerate(headers): ws1.write(0, col, h, fmt_header)
            
            if not df_p.empty:
                for idx, row in enumerate(df_p.itertuples(), 1):
                    ws1.write_row(idx, 0, [row.nama_aset, row.jenis_aset, row.kondisi_sipil, row.kondisi_me, row.Skor_Prioritas, row.Kelas_Prioritas, row.estimasi_biaya])
            
            # 2. SHEET MASTER
            app.get_master_aset().to_excel(writer, sheet_name='Master Data', index=False)
            
        st.download_button("Download Laporan Siap Cetak", buffer, "Laporan_Resmi_SIKI.xlsx")


