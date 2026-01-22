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
        # 1. Tabel Aset Fisik (Update: Tambah Luas Layanan)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS aset_fisik (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kode_aset TEXT, nama_aset TEXT, jenis_aset TEXT, satuan TEXT,
                kondisi_b REAL DEFAULT 0, kondisi_rr REAL DEFAULT 0, kondisi_rb REAL DEFAULT 0,
                nilai_kinerja REAL DEFAULT 0, 
                luas_layanan REAL DEFAULT 0, -- KRITIKAL: Untuk pembobotan sesuai Permen
                file_kmz TEXT, detail_teknis TEXT, keterangan TEXT
            )
        ''')

        # 2. Tabel Non-Fisik (Tanam, P3A, SDM)
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_tanam (id INTEGER PRIMARY KEY, musim TEXT, luas_tanam REAL, realisasi REAL, padi REAL, palawija REAL)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_p3a (id INTEGER PRIMARY KEY, nama_p3a TEXT, desa TEXT, status TEXT, keaktifan TEXT, anggota INTEGER)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_sdm_sarana (id INTEGER PRIMARY KEY, jenis TEXT, nama TEXT, kondisi TEXT, ket TEXT)')
        
        # Auto-Migration (Menambah kolom luas_layanan jika belum ada)
        cek = self.cursor.execute("PRAGMA table_info(aset_fisik)").fetchall()
        cols = [c[1] for c in cek]
        if 'luas_layanan' not in cols: 
            self.cursor.execute("ALTER TABLE aset_fisik ADD COLUMN luas_layanan REAL DEFAULT 0")
        if 'detail_teknis' not in cols: self.cursor.execute("ALTER TABLE aset_fisik ADD COLUMN detail_teknis TEXT")
        self.conn.commit()

    # --- LOGIKA BARU: HITUNG IKSI SESUAI PERMEN 23/2015 ---
    def hitung_skor_iksi_lengkap(self):
        # 1. Skor Fisik (Bobot 45%) - MENGGUNAKAN WEIGHTED AVERAGE BERDASARKAN LUAS
        df_fisik = pd.read_sql("SELECT nilai_kinerja, luas_layanan FROM aset_fisik", self.conn)
        skor_fisik = 0
        if not df_fisik.empty:
            total_luas = df_fisik['luas_layanan'].sum()
            if total_luas > 0:
                # Rumus: Sum(Nilai * Luas) / Total Luas
                skor_fisik = (df_fisik['nilai_kinerja'] * df_fisik['luas_layanan']).sum() / total_luas
            else:
                skor_fisik = df_fisik['nilai_kinerja'].mean() # Fallback rata-rata biasa

        # 2. Skor Produktivitas Tanam (Bobot 15%) - Simulasi Sederhana
        df_tanam = pd.read_sql("SELECT * FROM data_tanam", self.conn)
        skor_tanam = 0
        if not df_tanam.empty:
            # Logic: Jika Realisasi > 80% Rencana = Bagus (100), dst
            def nilai_tanam(row):
                ratio = (row['realisasi'] / row['luas_tanam']) * 100 if row['luas_tanam'] > 0 else 0
                if ratio >= 90: return 100
                elif ratio >= 70: return 80
                else: return 60
            skor_tanam = df_tanam.apply(nilai_tanam, axis=1).mean()

        # 3. Sarana Penunjang (Bobot 10%)
        df_sarana = pd.read_sql("SELECT * FROM data_sdm_sarana WHERE jenis IN ('Sarana Kantor', 'Alat')", self.conn)
        skor_sarana = 60 # Default Cukup
        if not df_sarana.empty: skor_sarana = 80 # Asumsi jika data ada, berarti terinventarisir

        # 4. SDM (Bobot 15%)
        df_sdm = pd.read_sql("SELECT * FROM data_sdm_sarana WHERE jenis='Personil'", self.conn)
        skor_sdm = 60
        if len(df_sdm) >= 2: skor_sdm = 90 # Jika ada minimal 2 personil

        # 5. Dokumentasi (Bobot 5%)
        skor_dok = 70 # Asumsi standar

        # 6. P3A (Bobot 10%)
        df_p3a = pd.read_sql("SELECT * FROM data_p3a", self.conn)
        skor_p3a = 0
        if not df_p3a.empty:
            def nilai_p3a(row):
                val = 0
                if row['status'] == "Sudah": val += 50
                if row['keaktifan'] == "Aktif": val += 50
                elif row['keaktifan'] == "Sedang": val += 30
                return val
            skor_p3a = df_p3a.apply(nilai_p3a, axis=1).mean()

        # HITUNG TOTAL IKSI
        iksi_total = (skor_fisik * 0.45) + (skor_tanam * 0.15) + (skor_sarana * 0.10) + \
                     (skor_sdm * 0.15) + (skor_dok * 0.05) + (skor_p3a * 0.10)
        
        return {
            "Total IKSI": round(iksi_total, 2),
            "Rincian": {
                "Prasarana Fisik (45%)": round(skor_fisik, 2),
                "Produktivitas Tanam (15%)": round(skor_tanam, 2),
                "Sarana Penunjang (10%)": round(skor_sarana, 2),
                "Organisasi Personalia (15%)": round(skor_sdm, 2),
                "Dokumentasi (5%)": round(skor_dok, 2),
                "Kelembagaan P3A (10%)": round(skor_p3a, 2)
            }
        }

    # --- CRUD UPDATED (With Luas Layanan) ---
    def tambah_data_kompleks(self, nama, jenis, satuan, b, rr, rb, luas_layanan, detail_dict, file_kmz=None):
        try:
            total = b + rr + rb
            nilai = 0
            if total > 0: nilai = ((b * 100) + (rr * 70) + (rb * 50)) / total
            
            kmz_name = file_kmz.name if file_kmz else "-"
            detail_json = json.dumps(detail_dict)
            
            self.cursor.execute('''INSERT INTO aset_fisik 
                (nama_aset, jenis_aset, satuan, kondisi_b, kondisi_rr, kondisi_rb, nilai_kinerja, luas_layanan, detail_teknis, file_kmz)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (nama, jenis, satuan, b, rr, rb, round(nilai, 2), luas_layanan, detail_json, kmz_name))
            self.conn.commit()
            return "✅ Data Fisik Tersimpan (Sesuai Regulasi)!"
        except Exception as e: return f"❌ Gagal: {e}"

    # --- FUNGSI INPUT NON FISIK (TETAP SAMA) ---
    def tambah_data_tanam(self, musim, luas, real, padi, pala):
        try:
            self.cursor.execute("INSERT INTO data_tanam VALUES (NULL, ?,?,?,?,?)", (musim, luas, real, padi, pala))
            self.conn.commit()
            return "✅ Tersimpan"
        except Exception as e: return str(e)

    def tambah_data_p3a(self, nm, ds, st, akt, ang):
        try:
            self.cursor.execute("INSERT INTO data_p3a VALUES (NULL, ?,?,?,?,?)", (nm, ds, st, akt, ang))
            self.conn.commit()
            return "✅ Tersimpan"
        except Exception as e: return str(e)
        
    def tambah_sdm_sarana(self, jns, nm, cond, ket):
        try:
            self.cursor.execute("INSERT INTO data_sdm_sarana VALUES (NULL, ?,?,?,?)", (jns, nm, cond, ket))
            self.conn.commit()
            return "✅ Tersimpan"
        except Exception as e: return str(e)

    # --- UTILS (Reset, JSON, Getters) ---
    def hapus_semua_data(self):
        for t in ['aset_fisik', 'data_tanam', 'data_p3a', 'data_sdm_sarana']:
            self.cursor.execute(f"DELETE FROM {t}"); self.cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{t}'")
        self.conn.commit()
        return "✅ Database Bersih"
        
    def get_data(self): return pd.read_sql("SELECT * FROM aset_fisik", self.conn)
    def get_table_data(self, t): return pd.read_sql(f"SELECT * FROM {t}", self.conn)
    def export_ke_json(self): return pd.read_sql("SELECT * FROM aset_fisik", self.conn).to_json(orient='records')
    def import_dari_json(self, f):
        try:
            df = pd.read_json(f)
            self.cursor.execute("DELETE FROM aset_fisik")
            df.to_sql('aset_fisik', self.conn, if_exists='append', index=False)
            self.conn.commit()
            return "✅ Restore Sukses"
        except Exception as e: return str(e)
    def update_data(self, df):
        self.cursor.execute("DELETE FROM aset_fisik")
        df.to_sql('aset_fisik', self.conn, if_exists='append', index=False)
        self.conn.commit()
