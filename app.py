import streamlit as st
import pandas as pd
from modules.backend import IrigasiBackend
import os

# Konfigurasi Halaman
st.set_page_config(page_title="Sistem Manajemen Aset Irigasi", layout="wide")
st.title("🌊 Sistem Informasi Kinerja Irigasi (SIKI)")

# Inisialisasi Backend
if 'backend' not in st.session_state:
    st.session_state.backend = IrigasiBackend()
app = st.session_state.backend

# --- SIDEBAR MENU ---
menu = st.sidebar.radio("Menu Navigasi", ["Dashboard", "Input Data Inventaris", "Analisa Kinerja", "Export Laporan"])

# --- HALAMAN DASHBOARD ---
if menu == "Dashboard":
    st.header("Ringkasan Daerah Irigasi")
    df = app.get_data()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Aset Terdata", f"{len(df)} Unit")
    
    rata_kinerja = df['nilai_kinerja'].mean() if not df.empty else 0
    col2.metric("Rata-rata Kinerja Fisik", f"{rata_kinerja:.2f}%")
    
    rusak_berat = len(df[df['nilai_kinerja'] < 60]) if not df.empty else 0
    col3.metric("Aset Rusak Berat", f"{rusak_berat} Unit", delta_color="inverse")

    if not df.empty:
        st.subheader("Sebaran Kondisi Aset")
        st.bar_chart(df.groupby('jenis_aset')['nilai_kinerja'].mean())

# --- HALAMAN INPUT DATA ---
elif menu == "Input Data Inventaris":
    st.header("Database Aset Irigasi")
    
    # Tombol Import Data Lama
    with st.expander("Import Data Lama (Sekali Saja)"):
        st.info("Pastikan file .xls/.csv lama sudah ada di folder 'data_lama'")
        if st.button("Jalankan Import Data Lama"):
            hasil = app.import_data_lama("data_lama")
            st.success(hasil)
            st.rerun()

    # Tabel Editor Utama
    st.write("Silakan edit kondisi aset di bawah ini (Klik dua kali pada sel):")
    df = app.get_data()
    
    # Konfigurasi kolom agar mudah diedit
    edited_df = st.data_editor(
        df,
        column_config={
            "kondisi_b": st.column_config.NumberColumn("Kondisi Baik", help="Volume/Jumlah Baik"),
            "kondisi_rr": st.column_config.NumberColumn("Rusak Ringan", help="Volume/Jumlah RR"),
            "kondisi_rb": st.column_config.NumberColumn("Rusak Berat", help="Volume/Jumlah RB"),
            "nilai_kinerja": st.column_config.ProgressColumn("Nilai Kinerja", min_value=0, max_value=100, format="%.2f%%"),
        },
        disabled=["id", "nilai_kinerja"], # Nilai kinerja gak boleh diedit manual, harus dihitung
        hide_index=True,
        num_rows="dynamic"
    )

    if st.button("Simpan Perubahan"):
        app.update_data(edited_df)
        app.hitung_ulang_kinerja() # Otomatis hitung ulang saat simpan
        st.success("Data berhasil disimpan & Nilai Kinerja diperbarui!")
        st.rerun()

# --- HALAMAN ANALISA KINERJA ---
elif menu == "Analisa Kinerja":
    st.header("Analisa Kinerja & Prioritas")
    df = app.get_data()
    
    if df.empty:
        st.warning("Data kosong.")
    else:
        # Filter Prioritas
        st.subheader("Rekomendasi Penanganan (Prioritas)")
        prioritas_df = df[df['nilai_kinerja'] < 60].sort_values(by='nilai_kinerja')
        
        st.write("Daftar aset yang **WAJIB** segera ditangani (Rusak Berat):")
        st.dataframe(prioritas_df[['nama_aset', 'jenis_aset', 'nilai_kinerja', 'keterangan']], use_container_width=True)

# --- HALAMAN EXPORT ---
elif menu == "Export Laporan":
    st.header("Cetak Laporan (Blangko)")
    
    st.write("Download data hasil analisa ke format Excel.")
    
    if st.button("Generate Laporan Excel"):
        df = app.get_data()
        
        # Proses Export Simple ke Excel
        output_file = 'output/Laporan_Kinerja_Terbaru.xlsx'
        
        # Menggunakan ExcelWriter untuk formatting sederhana
        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Blangko 1-P', index=False)
            
        with open(output_file, "rb") as file:
            btn = st.download_button(
                label="📥 Download File Excel",
                data=file,
                file_name="Laporan_Kinerja_Irigasi.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )