import sqlite3
import pandas as pd
import os

class IrigasiBackend:
    def __init__(self, db_path='database/irigasi.db'):
        # Auto-create folder DB
        self.db_folder = os.path.dirname(db_path)
        if self.db_folder and not os.path.exists(self.db_folder):
            try:
                os.makedirs(self.db_folder)
            except OSError: pass

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_db()

    def init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS aset_fisik (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kode_aset TEXT,
                nama_aset TEXT,
                jenis_aset TEXT,
                dimensi REAL DEFAULT 0,
                satuan TEXT,
                kondisi_b REAL DEFAULT 0,
                kondisi_rr REAL DEFAULT 0,
                kondisi_rb REAL DEFAULT 0,
                nilai_kinerja REAL DEFAULT 0,
                file_kmz TEXT,  -- Kolom baru untuk simpan nama file KMZ
                keterangan TEXT
            )
        ''')
        self.conn.commit()

    # --- FITUR BARU: TAMBAH DATA MANUAL ---
    def tambah_data_baru(self, nama, jenis, satuan, b, rr, rb, file_kmz=None):
        try:
            # Hitung kinerja otomatis saat input
            total = b + rr + rb
            nilai = 0
            if total > 0:
                nilai = ((b * 100) + (rr * 70) + (rb * 50)) / total
            
            kmz_name = file_kmz.name if file_kmz else "-"

            self.cursor.execute('''
                INSERT INTO aset_fisik (nama_aset, jenis_aset, satuan, kondisi_b, kondisi_rr, kondisi_rb, nilai_kinerja, file_kmz)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nama, jenis, satuan, b, rr, rb, round(nilai, 2), kmz_name))
            self.conn.commit()
            return "✅ Data Berhasil Disimpan!"
        except Exception as e:
            return f"❌ Gagal Simpan: {e}"

    def import_data_lama(self, folder_path):
        # (Kode import lama biarkan saja di sini seperti sebelumnya)
        # Copy dari backend.py sebelumnya
        pass 

    def get_data(self):
        return pd.read_sql("SELECT * FROM aset_fisik", self.conn)

    def update_data(self, df_edited):
        try:
            self.cursor.execute("DELETE FROM aset_fisik")
            df_edited.to_sql('aset_fisik', self.conn, if_exists='append', index=False)
            self.conn.commit()
        except Exception as e:
            print(f"Gagal update: {e}")
