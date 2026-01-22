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
        # 1. Tabel Aset Fisik (Lama)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS aset_fisik (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kode_aset TEXT, nama_aset TEXT, jenis_aset TEXT, satuan TEXT,
                kondisi_b REAL DEFAULT 0, kondisi_rr REAL DEFAULT 0, kondisi_rb REAL DEFAULT 0,
                nilai_kinerja REAL DEFAULT 0, file_kmz TEXT, detail_teknis TEXT, keterangan TEXT
            )
        ''')

        # 2. Tabel Non-Fisik (Baru)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_tanam (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                musim_tanam TEXT, luas_tanam_ha REAL, realisasi_tanam_ha REAL,
                produktivitas_padi REAL, produktivitas_palawija REAL
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_p3a (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama_p3a TEXT, desa TEXT, status_badan_hukum TEXT,
                keaktifan TEXT, jumlah_anggota INTEGER
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_sdm_sarana (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jenis_data TEXT, nama_item TEXT, jabatan_kondisi TEXT, keterangan TEXT
            )
        ''')
        
        # Cek kolom legacy
        cek = self.cursor.execute("PRAGMA table_info(aset_fisik)").fetchall()
        cols = [c[1] for c in cek]
        if 'detail_teknis' not in cols: self.cursor.execute("ALTER TABLE aset_fisik ADD COLUMN detail_teknis TEXT")
        if 'file_kmz' not in cols: self.cursor.execute("ALTER TABLE aset_fisik ADD COLUMN file_kmz TEXT")
        self.conn.commit()

    # --- INPUT ASET FISIK (LENGKAP) ---
    def tambah_data_kompleks(self, nama, jenis, satuan, b, rr, rb, detail_dict, file_kmz=None):
        try:
            total = b + rr + rb
            nilai = 0
            if total > 0: nilai = ((b * 100) + (rr * 70) + (rb * 50)) / total
            kmz_name = file_kmz.name if file_kmz else "-"
            detail_json = json.dumps(detail_dict)
            self.cursor.execute('''INSERT INTO aset_fisik (nama_aset, jenis_aset, satuan, kondisi_b, kondisi_rr, kondisi_rb, nilai_kinerja, detail_teknis, file_kmz)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (nama, jenis, satuan, b, rr, rb, round(nilai, 2), detail_json, kmz_name))
            self.conn.commit()
            return "✅ Data Fisik Tersimpan!"
        except Exception as e: return f"❌ Gagal: {e}"

    # --- INPUT DATA NON-FISIK ---
    def tambah_data_tanam(self, musim, luas, realisasi, padi, palawija):
        try:
            self.cursor.execute("INSERT INTO data_tanam (musim_tanam, luas_tanam_ha, realisasi_tanam_ha, produktivitas_padi, produktivitas_palawija) VALUES (?,?,?,?,?)",
                                (musim, luas, realisasi, padi, palawija))
            self.conn.commit()
            return "✅ Data Tanam Tersimpan!"
        except Exception as e: return f"❌ Gagal: {e}"

    def tambah_data_p3a(self, nama, desa, status, aktif, anggota):
        try:
            self.cursor.execute("INSERT INTO data_p3a (nama_p3a, desa, status_badan_hukum, keaktifan, jumlah_anggota) VALUES (?,?,?,?,?)",
                                (nama, desa, status, aktif, anggota))
            self.conn.commit()
            return "✅ Data P3A Tersimpan!"
        except Exception as e: return f"❌ Gagal: {e}"

    def tambah_sdm_sarana(self, jenis, nama, jabatan_kondisi, ket):
        try:
            self.cursor.execute("INSERT INTO data_sdm_sarana (jenis_data, nama_item, jabatan_kondisi, keterangan) VALUES (?,?,?,?)",
                                (jenis, nama, jabatan_kondisi, ket))
            self.conn.commit()
            return "✅ Data Tersimpan!"
        except Exception as e: return f"❌ Gagal: {e}"

    # --- FITUR JSON BACKUP (DIKEMBALIKAN) ---
    def export_ke_json(self):
        # Saat ini backup tabel fisik dulu (prioritas)
        return pd.read_sql("SELECT * FROM aset_fisik", self.conn).to_json(orient='records')

    def import_dari_json(self, f):
        try:
            df = pd.read_json(f)
            self.cursor.execute("DELETE FROM aset_fisik")
            df.to_sql('aset_fisik', self.conn, if_exists='append', index=False)
            self.conn.commit()
            return "✅ Restore Berhasil!"
        except Exception as e: return str(e)

    # --- FITUR RESET DATA (DIKEMBALIKAN) ---
    def hapus_semua_data(self):
        try:
            tables = ['aset_fisik', 'data_tanam', 'data_p3a', 'data_sdm_sarana']
            for t in tables:
                self.cursor.execute(f"DELETE FROM {t}")
                self.cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{t}'")
            self.conn.commit()
            return "✅ Database Bersih Total!"
        except: return "Gagal."

    # --- GETTERS ---
    def get_data(self): return pd.read_sql("SELECT * FROM aset_fisik", self.conn)
    def get_table_data(self, t): 
        try: return pd.read_sql(f"SELECT * FROM {t}", self.conn) 
        except: return pd.DataFrame()
    def update_data(self, df): self.update_table_data('aset_fisik', df)
    def update_table_data(self, t, df):
        self.cursor.execute(f"DELETE FROM {t}")
        df.to_sql(t, self.conn, if_exists='append', index=False)
        self.conn.commit()
