import streamlit as st
import pandas as pd
from modules.backend import IrigasiBackend
import io

st.set_page_config(page_title="SIKI - Sistem Irigasi", layout="wide")
st.title("🌊 Sistem Informasi Kinerja Irigasi (SIKI)")

if 'backend' not in st.session_state:
    st.session_state.backend = IrigasiBackend()
app = st.session_state.backend

# --- SIDEBAR ---
menu = st.sidebar.radio("Menu Navigasi", ["Dashboard", "Input Data Inventaris", "Analisa Kinerja", "Export Laporan"])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.header("Ringkasan Daerah Irigasi")
    df = app.get_data()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Aset", f"{len(df)} Unit")
    col2.metric("Rata-rata Kinerja", f"{df['nilai_kinerja'].mean() if not df.empty else 0:.2f}%")
    col3.metric("Rusak Berat", f"{len(df[df['nilai_kinerja'] < 60]) if not df.empty else 0} Unit")

    if not df.empty:
        st.subheader("Grafik Kondisi")
        st.bar_chart(df.groupby('jenis_aset')['nilai_kinerja'].mean())

# --- HALAMAN INPUT DATA (BARU!) ---
elif menu == "Input Data Inventaris":
    st.header("Manajemen Data Aset")
    
    # Buat TAB supaya rapi
    tab1, tab2 = st.tabs(["📝 Tambah Data Baru (Manual)", "📊 Edit Data Tabel"])
    
    # --- TAB 1: FORM INPUT MANUAL ---
    with tab1:
        st.write("Silakan isi formulir di bawah ini untuk menambahkan aset baru.")
        
        with st.form("form_tambah_aset"):
            col_a, col_b = st.columns(2)
            
            with col_a:
                nama_input = st.text_input("Nama Aset / Bangunan", placeholder="Contoh: Bendung Way Seputih")
                jenis_input = st.selectbox("Jenis Aset", ["Bendung", "Saluran Primer", "Saluran Sekunder", "Saluran Tersier", "Bangunan Bagi", "Bangunan Sadap", "Jembatan", "Gorong-Gorong", "Lainnya"])
                kmz_file = st.file_uploader("Upload File Peta (KMZ/KML)", type=["kmz", "kml"])
                
            with col_b:
                satuan_input = st.selectbox("Satuan", ["Buah (bh)", "Meter (m)", "Unit"])
                st.write("**Volume Kerusakan:**")
                b_input = st.number_input("Kondisi Baik", min_value=0.0, step=1.0)
                rr_input = st.number_input("Rusak Ringan", min_value=0.0, step=1.0)
                rb_input = st.number_input("Rusak Berat", min_value=0.0, step=1.0)
            
            submitted = st.form_submit_button("💾 SIMPAN DATA ASET")
            
            if submitted:
                if nama_input:
                    pesan = app.tambah_data_baru(
                        nama_input, jenis_input, satuan_input, 
                        b_input, rr_input, rb_input, kmz_file
                    )
                    if "Berhasil" in pesan:
                        st.success(pesan)
                    else:
                        st.error(pesan)
                else:
                    st.warning("Nama Aset tidak boleh kosong!")

    # --- TAB 2: EDIT DATA TABEL (YANG LAMA) ---
    with tab2:
        st.write("Edit data masal langsung di tabel:")
        df = app.get_data()
        
        if df.empty:
            st.info("Belum ada data. Silakan isi di Tab 'Tambah Data Baru'.")
        else:
            edited_df = st.data_editor(
                df,
                column_config={
                    "nilai_kinerja": st.column_config.ProgressColumn("Kinerja", format="%.2f%%", min_value=0, max_value=100),
                    "file_kmz": st.column_config.TextColumn("File Peta", disabled=True)
                },
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True
            )
            
            if st.button("Simpan Perubahan Tabel"):
                app.update_data(edited_df)
                st.success("Tabel berhasil diupdate!")
                st.rerun()

# --- ANALISA KINERJA ---
elif menu == "Analisa Kinerja":
    st.header("Analisa Prioritas")
    df = app.get_data()
    if not df.empty:
        prioritas = df[df['nilai_kinerja'] < 60]
        if not prioritas.empty:
            st.error("PERHATIAN: Aset berikut butuh penanganan segera (Rusak Berat):")
            st.dataframe(prioritas)
        else:
            st.success("Semua aset dalam kondisi aman (Kinerja > 60%).")
    else:
        st.warning("Data kosong.")

# --- EXPORT LAPORAN ---
elif menu == "Export Laporan":
    st.header("Cetak Laporan (Format Blangko)")
    st.write("Data yang Kakak input manual akan otomatis masuk ke format Excel standar.")
    
    if st.button("Download Excel Blangko 1-P"):
        df = app.get_data()
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            # Disini nanti kita mapping kolom DF ke kolom Excel Template
            # Untuk sekarang kita dump dulu datanya
            df.to_excel(writer, sheet_name='Laporan', index=False)
            
        st.download_button("📥 Download Excel", buffer, "Laporan_SIKI.xlsx")
