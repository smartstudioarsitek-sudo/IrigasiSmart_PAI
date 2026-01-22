import xlsxwriter
import os

# Pastikan folder templates ada
if not os.path.exists('templates'):
    os.makedirs('templates')

# Nama file template
filename = 'templates/template_1p.xlsx'
workbook = xlsxwriter.Workbook(filename)
worksheet = workbook.add_worksheet("Blangko 1-P Fisik")

# --- 1. SETUP FORMATTING (GAYA HURUF & GARIS) ---
# Format Header Utama
header_format = workbook.add_format({
    'bold': True, 'align': 'center', 'valign': 'vcenter', 
    'font_size': 12, 'font_name': 'Arial'
})
# Format Judul Tabel (Kuning, Bold, Border)
table_header_format = workbook.add_format({
    'bold': True, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
    'border': 1, 'bg_color': '#FFC000', 'font_size': 10
})
# Format Isi Tabel (Biasa)
cell_format = workbook.add_format({
    'border': 1, 'font_size': 10, 'font_name': 'Arial'
})
# Format Angka Tengah (Center)
center_format = workbook.add_format({
    'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 10
})

# --- 2. SET LEBAR KOLOM ---
worksheet.set_column('A:A', 5)   # No
worksheet.set_column('B:B', 30)  # Nama Aset
worksheet.set_column('C:C', 15)  # Jenis
worksheet.set_column('D:D', 10)  # Volume
worksheet.set_column('E:E', 10)  # Satuan
worksheet.set_column('F:H', 12)  # Kondisi (B/RR/RB)
worksheet.set_column('I:I', 15)  # Nilai Kinerja
worksheet.set_column('J:J', 25)  # Keterangan

# --- 3. MEMBUAT KOP SURAT (HEADER) ---
# Ini meniru kop surat standar laporan PU
worksheet.merge_range('A1:J1', 'LAPORAN KINERJA SISTEM IRIGASI (ASPEK PRASARANA FISIK)', header_format)
worksheet.merge_range('A2:J2', 'DAERAH IRIGASI: ...........................................', header_format)
worksheet.merge_range('A3:J3', 'KABUPATEN/KOTA: ...........................................', header_format)

# --- 4. MEMBUAT JUDUL TABEL (HEADER TABLE) ---
# Baris 5 (Header Utama)
worksheet.merge_range('A5:A6', 'NO', table_header_format)
worksheet.merge_range('B5:B6', 'NAMA BANGUNAN / RUAS SALURAN', table_header_format)
worksheet.merge_range('C5:C6', 'JENIS ASET', table_header_format)
worksheet.merge_range('D5:E5', 'DIMENSI / VOLUME', table_header_format)
worksheet.merge_range('F5:H5', 'KONDISI FISIK (Bobot %)', table_header_format)
worksheet.merge_range('I5:I6', 'NILAI KINERJA', table_header_format)
worksheet.merge_range('J5:J6', 'KETERANGAN / REKOMENDASI', table_header_format)

# Baris 6 (Sub-Header)
worksheet.write('D6', 'Jml', table_header_format)
worksheet.write('E6', 'Sat', table_header_format)
worksheet.write('F6', 'B', table_header_format)  # Baik
worksheet.write('G6', 'RR', table_header_format) # Rusak Ringan
worksheet.write('H6', 'RB', table_header_format) # Rusak Berat

# --- 5. MENUTUP FILE ---
workbook.close()
print(f"✅ Sukses! File template telah dibuat di: {filename}")