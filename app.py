import streamlit as st
import pandas as pd
from modules.backend import IrigasiBackend
import os

# Konfigurasi Halaman
st.set_page_config(page_title="SIKI - Sistem Irigasi", layout="wide")
st.title("🌊 Sistem Informasi Kinerja Irigasi (SIKI)")

# Inisialisasi Backend
if 'backend' not in st.session_state:
    st.session_state.backend = IrigasiBackend()
app = st.session_state.backend

# --- SIDEBAR MENU ---
menu = st.sidebar.radio("Menu Navigasi", ["Dashboard", "Input Data Inventaris", "Analisa Kinerja", "Export Laporan"])

# --- DEBUGGING TOOLS (BANTUAN) ---
with st.sidebar.expander("🛠️ Menu Teknisi (Cek Data)"):
    st.write("Gunakan ini untuk mengecek apakah file data lama terbaca.")
    if st.button("Cek Folder 'data_lama'"):
        folder = "data_lama"
        if os.path.exists(folder):
            files = os.listdir(folder)
            st.success(f"Folder DITEMUKAN! Isi {len(files)} file.")
            st.write(files[:5]) # Tampilkan 5 file pertama
        else:
            st.error("❌ Folder 'data_lama' TIDAK DITEMUKAN. Pastikan sudah di-upload ke GitHub!")

# --- HALAMAN DASHBOARD ---
if menu == "Dashboard":
    st.header("Ringkasan Daerah Irigasi")
    df = app.get_data()
    
    col1, col2, col3 = st.columns(3)
    # Gunakan 0 jika data kosong
    total_aset = len(df) if not df.empty else 0
    rata_kinerja = df['nilai_kinerja'].mean() if not df.empty else 0
    rusak_berat = len(df[df['nilai_kinerja'] < 60]) if not df.empty else 0

    col1.metric("Total Aset Terdata", f"{total_aset} Unit")
    col2.metric("Rata-rata Kinerja Fisik", f"{rata_kinerja:.2f}%")
    col3.metric("Aset Rusak Berat", f"{rusak_berat} Unit", delta_color="inverse")

    if not df.empty:
        st.subheader("Sebaran Kondisi Aset")
        try:
            st.bar_chart(df.groupby('jenis_aset')['nilai_kinerja'].mean())
        except:
            st.info("Grafik belum tersedia (data belum cukup).")

# --- HALAMAN INPUT DATA ---
elif menu == "Input Data Inventaris":
    st.header("Database Aset Irigasi")
    
    # Tombol Import Data Lama
    with st.expander("📥 Import Data Lama (Klik Disini)", expanded=True):
        st.info("Pastikan file .xls/.csv lama sudah ada di folder 'data_lama' di GitHub.")
        if st.button("JALANKAN IMPORT SEKARANG"):
            with st.spinner("Sedang membaca file lama..."):
                hasil = app.import_data_lama("data_lama")
                if "ERROR" in hasil:
                    st.error(hasil)
                else:
                    st.success(hasil)
                    st.balloons()
                    # Refresh halaman manual pakai query param trik (opsional) atau user klik menu lain

    # Tabel Editor Utama
    st.divider()
    st.write("### Editor Data Kondisi")
    df = app.get_data()
    
    if df.empty:
        st.warning("Data masih kosong. Silakan Import Data Lama dulu di atas.")
    else:
        # Konfigurasi kolom
        edited_df = st.data_editor(
            df,
            column_config={
                "nama_aset": st.column_config.TextColumn("Nama Aset", width="large", disabled=True),
                "jenis_aset": st.column_config.TextColumn("Jenis", width="small", disabled=True),
                "kondisi_b": st.column_config.NumberColumn("Baik (m/bh)", help="Volume kondisi Baik", min_value=0),
                "kondisi_rr": st.column_config.NumberColumn("R.Ringan (m/bh)", help="Volume Rusak Ringan", min_value=0),
                "kondisi_rb": st.column_config.NumberColumn("R.Berat (m/bh)", help="Volume Rusak Berat", min_value=0),
                "nilai_kinerja": st.column_config.ProgressColumn("Nilai Kinerja", min_value=0, max_value=100, format="%.2f%%"),
            },
            disabled=["id", "kode_aset", "nilai_kinerja"], 
            hide_index=True,
            num_rows="dynamic",
            use_container_width=True
        )

        if st.button("💾 SIMPAN PERUBAHAN & HITUNG ULANG"):
            app.update_data(edited_df)
            app.hitung_ulang_kinerja()
            st.success("Data berhasil disimpan! Nilai kinerja sudah diperbarui.")
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
        try:
            # Filter yang rusak berat (Nilai < 60)
            prioritas_df = df[df['nilai_kinerja'] < 60].sort_values(by='nilai_kinerja')
            
            if prioritas_df.empty:
                st.success("🎉 Tidak ada aset yang Rusak Berat (Kinerja < 60).")
            else:
                st.error(f"Ditemukan {len(prioritas_df)} aset KRITIS yang butuh penanganan segera:")
                st.dataframe(
                    prioritas_df[['nama_aset', 'jenis_aset', 'nilai_kinerja', 'kondisi_rb']], 
                    use_container_width=True,
                    hide_index=True
                )
        except Exception as e:
            st.error(f"Terjadi kesalahan filter: {e}")

# --- HALAMAN EXPORT ---
elif menu == "Export Laporan":
    st.header("Cetak Laporan (Excel)")
    
    if st.button("Generate File Excel"):
        df = app.get_data()
        
        # Simpan ke memori buffer (agar tidak perlu file temp)
        # Sederhana saja pakai pandas to_excel default dulu
        import io
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Laporan Fisik', index=False)
            
        st.download_button(
            label="📥 Download Laporan Excel",
            data=buffer,
            file_name="Laporan_Kinerja_Irigasi_Terbaru.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
