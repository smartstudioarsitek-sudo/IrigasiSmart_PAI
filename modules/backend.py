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
        # Auto-create table
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
                file_kmz TEXT,
                keterangan TEXT
            )
        ''')
        # Auto-add column file_kmz if missing
        cek = self.cursor.execute("PRAGMA table_info(aset_fisik)").fetchall()
        cols = [c[1] for c in cek]
        if 'file_kmz' not in cols:
            try:
                self.cursor.execute("ALTER TABLE aset_fisik ADD COLUMN file_kmz TEXT")
                self.conn.commit()
            except: pass

    # --- FITUR JSON (SAVE & OPEN) ---
    def export_ke_json(self):
        """Mengambil semua data dan mengubahnya jadi string JSON"""
        df = pd.read_sql("SELECT * FROM aset_fisik", self.conn)
        return df.to_json(orient='records')

    def import_dari_json(self, json_file):
        """Membaca file JSON dan menimpa database"""
        try:
            df = pd.read_json(json_file)
            # Bersihkan database lama
            self.cursor.execute("DELETE FROM aset_fisik")
            # Masukkan data baru
            df.to_sql('aset_fisik', self.conn, if_exists='append', index=False)
            self.conn.commit()
            return f"✅ Berhasil Restore! {len(df)} data telah dimuat."
        except Exception as e:
            return f"❌ Gagal Import JSON: {e}"

    # --- FITUR CRUD LAINNYA ---
    def tambah_data_baru(self, nama, jenis, satuan, b, rr, rb, file_kmz=None):
        try:
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
        # (Kode import data excel lama tetap sama seperti sebelumnya)
        # Saya singkat disini biar tidak kepanjangan, pakai kode import yang terakhir ya kak.
        pass 

    def hitung_ulang_kinerja(self):
        df = pd.read_sql("SELECT * FROM aset_fisik", self.conn)
        if df.empty: return df
        def rumus(row):
            b, rr, rb = row.get('kondisi_b', 0), row.get('kondisi_rr', 0), row.get('kondisi_rb', 0)
            total = b + rr + rb
            if total == 0: return 0.0
            return round(((b * 100) + (rr * 70) + (rb * 50)) / total, 2)
        df['nilai_kinerja'] = df.apply(rumus, axis=1)
        data = [(row['nilai_kinerja'], row['id']) for _, row in df.iterrows()]
        self.cursor.executemany('UPDATE aset_fisik SET nilai_kinerja = ? WHERE id = ?', data)
        self.conn.commit()
        return df

    def get_data(self):
        return pd.read_sql("SELECT * FROM aset_fisik", self.conn)

    def update_data(self, df_edited):
        self.cursor.execute("DELETE FROM aset_fisik")
        df_edited.to_sql('aset_fisik', self.conn, if_exists='append', index=False)
        self.conn.commit()
