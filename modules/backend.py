import sqlite3
import pandas as pd
import os
import json

class IrigasiBackend:
    def __init__(self, db_path='database/irigasi.db'):
        self.db_folder = os.path.dirname(db_path)
        if self.db_folder and not os.path.exists(self.db_folder):
            try:
                os.makedirs(self.db_folder)
            except OSError: pass

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_db()

    def init_db(self):
        # Tabel Utama
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS aset_fisik (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kode_aset TEXT,
                nama_aset TEXT,
                jenis_aset TEXT,
                satuan TEXT,
                kondisi_b REAL DEFAULT 0,
                kondisi_rr REAL DEFAULT 0,
                kondisi_rb REAL DEFAULT 0,
                nilai_kinerja REAL DEFAULT 0,
                file_kmz TEXT,
                detail_teknis TEXT, -- Kolom baru untuk simpan dimensi (b, h, m, dll)
                keterangan TEXT
            )
        ''')
        # Auto-Migration: Cek kolom baru
        cek = self.cursor.execute("PRAGMA table_info(aset_fisik)").fetchall()
        cols = [c[1] for c in cek]
        if 'detail_teknis' not in cols:
            self.cursor.execute("ALTER TABLE aset_fisik ADD COLUMN detail_teknis TEXT")
        if 'file_kmz' not in cols:
            self.cursor.execute("ALTER TABLE aset_fisik ADD COLUMN file_kmz TEXT")
        self.conn.commit()

    # --- SIMPAN DATA DENGAN DETAIL TEKNIS ---
    def tambah_data_kompleks(self, nama, jenis, satuan, b, rr, rb, detail_dict, file_kmz=None):
        try:
            total = b + rr + rb
            nilai = 0
            if total > 0:
                nilai = ((b * 100) + (rr * 70) + (rb * 50)) / total
            
            kmz_name = file_kmz.name if file_kmz else "-"
            
            # Konversi detail (dict) jadi Text JSON agar bisa masuk database
            detail_json = json.dumps(detail_dict)

            self.cursor.execute('''
                INSERT INTO aset_fisik (nama_aset, jenis_aset, satuan, kondisi_b, kondisi_rr, kondisi_rb, nilai_kinerja, detail_teknis, file_kmz)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nama, jenis, satuan, b, rr, rb, round(nilai, 2), detail_json, kmz_name))
            self.conn.commit()
            return "✅ Data Berhasil Disimpan Lengkap!"
        except Exception as e:
            return f"❌ Gagal Simpan: {e}"

    # --- FITUR WAJIB LAINNYA (SAMA SEPERTI SEBELUMNYA) ---
    def hapus_semua_data(self):
        try:
            self.cursor.execute("DELETE FROM aset_fisik")
            self.cursor.execute("DELETE FROM sqlite_sequence WHERE name='aset_fisik'")
            self.conn.commit()
            return "✅ Database bersih!"
        except: return "Gagal."

    def get_data(self):
        return pd.read_sql("SELECT * FROM aset_fisik", self.conn)
        
    def export_ke_json(self):
        return pd.read_sql("SELECT * FROM aset_fisik", self.conn).to_json(orient='records')
        
    def import_dari_json(self, f):
        try:
            df = pd.read_json(f)
            self.cursor.execute("DELETE FROM aset_fisik")
            df.to_sql('aset_fisik', self.conn, if_exists='append', index=False)
            self.conn.commit()
            return "✅ Sukses Restore."
        except Exception as e: return str(e)

    def update_data(self, df):
        self.cursor.execute("DELETE FROM aset_fisik")
        df.to_sql('aset_fisik', self.conn, if_exists='append', index=False)
        self.conn.commit()
