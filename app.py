import streamlit as st
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from modules.backend import IrigasiBackend
import io
import json
import folium
from streamlit_folium import st_folium
import xml.etree.ElementTree as ET

st.set_page_config(page_title="SIKI - Sistem Irigasi", layout="wide")
st.title("🌊 Sistem Informasi Kinerja Irigasi (SIKI)")

if 'backend' not in st.session_state:
    st.session_state.backend = IrigasiBackend()
app = st.session_state.backend

# --- FUNGSI GAMBAR SKETSA TEKNIS (VISUALISASI) ---
def gambar_sketsa(jenis, params):
    """Menggambar sketsa teknik sederhana berdasarkan input"""
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.set_axis_off() # Hilangkan sumbu X/Y biar bersih seperti gambar teknik
    
    if jenis == "Saluran (Primer/Sekunder/Tersier)":
        # Gambar Penampang Trapesium
        b = params.get('b', 1.0) # Lebar dasar
        h = params.get('h', 1.0) # Tinggi
        m = params.get('m', 1.0) # Kemiringan
        
        # Koordinat Trapesium
        x = [0, m*h, m*h + b, 2*m*h + b]
        y = [h, 0, 0, h]
        
        ax.plot(x, y, 'k-', linewidth=2) # Garis tanah
        ax.plot([x[0]-1, x[3]+1], [h, h], 'g--', linewidth=1, label="Muka Tanah") # Garis atas
        
        # Label Dimensi
        ax.text((m*h + b/2), -0.2, f"b = {b} m", ha='center', color='blue')
        ax.text(m*h/2 - 0.2, h/2, f"h = {h} m", ha='right', color='red')
        
        ax.set_title(f"Sketsa Penampang Saluran ({params.get('tipe_lining','Tanah')})")
        
    elif jenis == "Bendung":
        # Gambar Sketsa Bendung Samping
        L = params.get('lebar_mercu', 10)
        H = params.get('tinggi_mercu', 2)
        
        # Gambar Body Bendung (Segitiga Sederhana)
        polygon = patches.Polygon([[0, 0], [2, H], [4, 0]], closed=True, edgecolor='black', facecolor='gray')
        ax.add_patch(polygon)
        
        # Garis Air
        ax.plot([-1, 2], [H, H], 'b-', linewidth=2) # Hulu
        ax.plot([4, 6], [0.5, 0.5], 'b--', linewidth=1) # Hilir
        
        ax.text(2, H+0.2, f"Mercu: {params.get('tipe_mercu','Bulat')}", ha='center')
        ax.text(2, H/2, f"H = {H} m", ha='center', color='white')
        ax.set_title("Sketsa Melintang Bendung")

    else:
        ax.text(0.5, 0.5, "Visualisasi belum tersedia untuk tipe ini", ha='center')
        
    return fig

# --- MENU DASHBOARD & LAINNYA (Sama seperti sebelumnya) ---
# ... (Kode Dashboard, Peta, Analisa biarkan sama / copy dari sebelumnya) ...
# Biar tidak kepanjangan, saya fokus ke MENU INPUT DATA yang baru saja

menu = st.sidebar.radio("Menu Navigasi", ["Dashboard", "Input Data Spesifik", "Peta Digital (GIS)", "Analisa Kinerja", "Export Laporan"])

# --- DASHBOARD SIMPLE (Supaya kode jalan) ---
if menu == "Dashboard":
    st.header("Dashboard Utama")
    df = app.get_data()
    st.metric("Total Aset", len(df))
    if not df.empty:
        st.bar_chart(df['nilai_kinerja'])

# --- HALAMAN INPUT DATA SPESIFIK (FITUR UTAMA) ---
elif menu == "Input Data Spesifik":
    st.header("📝 Input Data Aset (Sesuai Template)")
    
    t1, t2 = st.tabs(["Formulir Detail", "Data Tabel"])
    
    with t1:
        col_kiri, col_kanan = st.columns([1, 1])
        
        with col_kiri:
            st.subheader("1. Identitas Aset")
            jenis = st.selectbox("Pilih Jenis Bangunan:", 
                ["Saluran (Primer/Sekunder/Tersier)", "Bendung", "Bangunan Bagi/Sadap", "Jembatan", "Lainnya"])
            
            nama = st.text_input("Nama Aset / Ruas", placeholder="Contoh: Saluran Sekunder Ruas 1")
            file_peta = st.file_uploader("Upload Peta (KMZ/KML)", type=["kmz", "kml"])

            st.subheader("2. Detail Teknis (Dimensi)")
            
            # --- FORM DINAMIS BERDASARKAN JENIS ---
            detail_input = {} # Dictionary untuk simpan detail
            
            if jenis == "Saluran (Primer/Sekunder/Tersier)":
                st.info("Parameter sesuai Template 'saluran.xls'")
                panjang = st.number_input("Panjang Ruas (m)", min_value=0.0)
                q_max = st.number_input("Debit Rencana Q (m3/dt)", min_value=0.0)
                tipe_lining = st.selectbox("Tipe Lining", ["Tanah", "Pasangan Batu", "Beton", "Precast"])
                
                st.write("**Dimensi Penampang:**")
                c1, c2, c3 = st.columns(3)
                b = c1.number_input("Lebar Dasar (b)", value=1.0)
                h = c2.number_input("Tinggi Jagaan (h)", value=1.0)
                m = c3.number_input("Kemiringan Talud (m)", value=1.0)
                
                # Simpan ke dict
                detail_input = {"panjang": panjang, "q_max": q_max, "tipe_lining": tipe_lining, "b": b, "h": h, "m": m}
                satuan_input = "m" # Default satuan saluran
                
            elif jenis == "Bendung":
                st.info("Parameter sesuai Template 'bendung.xls'")
                tipe_mercu = st.selectbox("Tipe Mercu", ["Bulat", "Ogee", "Tajam"])
                lebar_mercu = st.number_input("Lebar Efektif Mercu (m)", min_value=0.0)
                tinggi_mercu = st.number_input("Tinggi Mercu dari Lantai (m)", value=2.0)
                kolam_olak = st.selectbox("Tipe Kolam Olak", ["USBR", "Vlughter", "Bucket"])
                
                detail_input = {"tipe_mercu": tipe_mercu, "lebar_mercu": lebar_mercu, "tinggi_mercu": tinggi_mercu, "kolam_olak": kolam_olak}
                satuan_input = "bh"

            else:
                st.write("Isi parameter umum:")
                dimensi_umum = st.text_input("Dimensi (Panjang/Lebar)")
                detail_input = {"dimensi_umum": dimensi_umum}
                satuan_input = "unit"

        with col_kanan:
            st.subheader("3. Visualisasi Sketsa")
            # Panggil fungsi gambar
            if detail_input:
                fig = gambar_sketsa(jenis, detail_input)
                st.pyplot(fig)
            else:
                st.warning("Isi data teknis untuk melihat sketsa.")
            
            st.divider()
            st.subheader("4. Kondisi Fisik")
            cb = st.number_input("Volume Baik", min_value=0.0)
            crr = st.number_input("Volume Rusak Ringan", min_value=0.0)
            crb = st.number_input("Volume Rusak Berat", min_value=0.0)
            
            if st.button("💾 SIMPAN DATA ASET", type="primary"):
                if nama:
                    msg = app.tambah_data_kompleks(nama, jenis, satuan_input, cb, crr, crb, detail_input, file_peta)
                    st.success(msg)
                else:
                    st.error("Nama Aset wajib diisi!")

    with t2:
        st.write("Database Aset:")
        df = app.get_data()
        st.dataframe(df)

# --- MENU LAIN (Copy Paste dari app.py sebelumnya untuk Peta, Reset, dll) ---
# ...
