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
        # 1. Tabel Aset Fisik (Tetap, dengan Luas Layanan)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS aset_fisik (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kode_aset TEXT, nama_aset TEXT, jenis_aset TEXT, satuan TEXT,
                kondisi_b REAL DEFAULT 0, kondisi_rr REAL DEFAULT 0, kondisi_rb REAL DEFAULT 0,
                nilai_kinerja REAL DEFAULT 0, luas_layanan REAL DEFAULT 0,
                file_kmz TEXT, detail_teknis TEXT, keterangan TEXT
            )
        ''')

        # 2. Tabel Tanam & Hidrologi (UPDATE: Tambah Faktor K & Debit)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_tanam (
                id INTEGER PRIMARY KEY,
                musim TEXT, -- MT1, MT2, MT3
                luas_rencana REAL, luas_realisasi REAL,
                debit_andalan REAL, -- Liter/detik (Q Tersedia)
                kebutuhan_air REAL, -- Liter/detik (Q Butuh)
                faktor_k REAL, -- Q Tersedia / Q Butuh
                prod_padi REAL, prod_palawija REAL
            )
        ''')

        # 3. Tabel P3A (Tetap)
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_p3a (id INTEGER PRIMARY KEY, nama_p3a TEXT, desa TEXT, status TEXT, keaktifan TEXT, anggota INTEGER)')
        
        # 4. Tabel SDM (Tetap)
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_sdm_sarana (id INTEGER PRIMARY KEY, jenis TEXT, nama TEXT, kondisi TEXT, ket TEXT)')

        # 5. Tabel Dokumentasi (BARU: Untuk Checklist Dokumen)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_dokumentasi (
                id INTEGER PRIMARY KEY,
                jenis_dokumen TEXT, -- Peta, Skema, Buku Data
                ada INTEGER -- 1=Ada, 0=Tidak
            )
        ''')
        
        # Auto-Migration Column Checks
        cek = self.cursor.execute("PRAGMA table_info(aset_fisik)").fetchall()
        cols = [c[1] for c in cek]
        if 'luas_layanan' not in cols: self.cursor.execute("ALTER TABLE aset_fisik ADD COLUMN luas_layanan REAL DEFAULT 0")
        if 'detail_teknis' not in cols: self.cursor.execute("ALTER TABLE aset_fisik ADD COLUMN detail_teknis TEXT")
        self.conn.commit()

    # --- HITUNG IKSI (ALGORITMA YANG DIPERBAIKI) ---
    def hitung_skor_iksi_audit(self):
        # 1. PRASARANA FISIK (45%) - Weighted by Area
        df_fisik = pd.read_sql("SELECT nilai_kinerja, luas_layanan FROM aset_fisik", self.conn)
        skor_fisik = 0
        total_luas_di = df_fisik['luas_layanan'].sum()
        
        if not df_fisik.empty:
            if total_luas_di > 0:
                skor_fisik = (df_fisik['nilai_kinerja'] * df_fisik['luas_layanan']).sum() / total_luas_di
            else:
                skor_fisik = df_fisik['nilai_kinerja'].mean()

        # 2. PRODUKTIVITAS TANAM (15%) - NOW WITH FAKTOR K!
        df_tanam = pd.read_sql("SELECT * FROM data_tanam", self.conn)
        skor_tanam = 0
        if not df_tanam.empty:
            def hitung_per_mt(row):
                # Sub-bot: Air (9%) + Luas (4%) + Prod (2%) = 15%
                # Normalisasi ke skala 100 dulu
                
                # A. Faktor K (Ketersediaan Air)
                fk = row['faktor_k']
                nilai_k = 100 if fk >= 1.0 else (80 if fk >= 0.7 else (60 if fk > 0 else 0))
                
                # B. Realisasi Tanam
                ratio_luas = (row['luas_realisasi'] / row['luas_rencana'] * 100) if row['luas_rencana'] > 0 else 0
                nilai_luas = 100 if ratio_luas >= 90 else (80 if ratio_luas >= 70 else 60)
                
                # C. Produktivitas (Yield)
                # Asumsi target padi 6 ton/ha
                nilai_prod = (row['prod_padi'] / 6 * 100)
                if nilai_prod > 100: nilai_prod = 100
                
                # Gabung (Bobot Relatif dalam Aspek Tanam)
                # K=60%, Luas=27%, Prod=13% (Approximation of 9:4:2)
                return (nilai_k * 0.60) + (nilai_luas * 0.27) + (nilai_prod * 0.13)
            
            skor_tanam = df_tanam.apply(hitung_per_mt, axis=1).mean()

        # 3. SARANA PENUNJANG (10%)
        df_sarana = pd.read_sql("SELECT * FROM data_sdm_sarana WHERE jenis IN ('Sarana Kantor', 'Alat', 'Transportasi')", self.conn)
        skor_sarana = 0
        # Simple Checklist logic: Ada Kantor? Ada Alat? Ada Kendaraan?
        items = df_sarana['nama'].str.lower().tolist()
        if any('kantor' in x for x in items): skor_sarana += 40
        if any('alat' in x for x in items): skor_sarana += 30
        if any('motor' in x or 'mobil' in x for x in items): skor_sarana += 30

        # 4. ORGANISASI PERSONALIA (15%) - LOGIKA DINAMIS
        df_sdm = pd.read_sql("SELECT * FROM data_sdm_sarana WHERE jenis='Personil'", self.conn)
        jml_personil = len(df_sdm)
        
        # Standar Permen: 1 Petugas OP per 750 Ha (Juru)
        kebutuhan_ideal = max(1, round(total_luas_di / 750)) 
        fulfillment = (jml_personil / kebutuhan_ideal) * 100
        
        skor_sdm = 100 if fulfillment >= 100 else fulfillment

        # 5. DOKUMENTASI (5%) - NO MORE HARDCODING!
        df_dok = pd.read_sql("SELECT * FROM data_dokumentasi", self.conn)
        skor_dok = 0
        if not df_dok.empty:
            jml_ada = df_dok['ada'].sum()
            total_item = len(df_dok)
            skor_dok = (jml_ada / total_item) * 100 if total_item > 0 else 0

        # 6. P3A (10%)
        df_p3a = pd.read_sql("SELECT * FROM data_p3a", self.conn)
        skor_p3a = 0
        if not df_p3a.empty:
            def nilai_p3a(row):
                v = 0
                if row['status'] == "Sudah": v += 50
                if row['keaktifan'] == "Aktif": v += 50
                elif row['keaktifan'] == "Sedang": v += 25
                return v
            skor_p3a = df_p3a.apply(nilai_p3a, axis=1).mean()

        # TOTAL FINAL
        iksi = (skor_fisik * 0.45) + (skor_tanam * 0.15) + (skor_sarana * 0.10) + \
               (skor_sdm * 0.15) + (skor_dok * 0.05) + (skor_p3a * 0.10)
        
        return {
            "Total IKSI": round(iksi, 2),
            "Rincian": {
                "Fisik (45%)": round(skor_fisik, 2),
                "Tanam (15%)": round(skor_tanam, 2),
                "Sarana (10%)": round(skor_sarana, 2),
                "SDM (15%)": round(skor_sdm, 2),
                "Dokumen (5%)": round(skor_dok, 2),
                "P3A (10%)": round(skor_p3a, 2)
            }
        }

    # --- INPUT BARU: TANAM DENGAN HIDROLOGI ---
    def tambah_data_tanam_lengkap(self, musim, luas_r, luas_real, q_andalan, q_butuh, padi, pala):
        try:
            # Hitung Faktor K Otomatis
            fk = q_andalan / q_butuh if q_butuh > 0 else 0
            self.cursor.execute("INSERT INTO data_tanam VALUES (NULL, ?,?,?,?,?,?,?)", 
                (musim, luas_r, luas_real, q_andalan, q_butuh, round(fk, 2), padi, pala))
            self.conn.commit()
            return f"✅ Data Tanam Tersimpan (Faktor K = {fk:.2f})"
        except Exception as e: return f"❌ Gagal: {e}"

    # --- INPUT BARU: DOKUMENTASI CHECKLIST ---
    def update_dokumentasi(self, checklist_dict):
        try:
            self.cursor.execute("DELETE FROM data_dokumentasi")
            for item, status in checklist_dict.items():
                val = 1 if status else 0
                self.cursor.execute("INSERT INTO data_dokumentasi (jenis_dokumen, ada) VALUES (?,?)", (item, val))
            self.conn.commit()
            return "✅ Status Dokumentasi Diupdate!"
        except Exception as e: return str(e)

    # --- FUNGSI EXISTING (CRUD LAMA) ---
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
            return "✅ Data Fisik Tersimpan!"
        except Exception as e: return str(e)

    def tambah_data_p3a(self, nm, ds, st, akt, ang):
        self.cursor.execute("INSERT INTO data_p3a VALUES (NULL, ?,?,?,?,?)", (nm, ds, st, akt, ang)); self.conn.commit()
        return "✅ Tersimpan"
    def tambah_sdm_sarana(self, jns, nm, cond, ket):
        self.cursor.execute("INSERT INTO data_sdm_sarana VALUES (NULL, ?,?,?,?)", (jns, nm, cond, ket)); self.conn.commit()
        return "✅ Tersimpan"
    def hapus_semua_data(self):
        for t in ['aset_fisik','data_tanam','data_p3a','data_sdm_sarana','data_dokumentasi']:
            self.cursor.execute(f"DELETE FROM {t}"); self.cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{t}'")
        self.conn.commit()
        return "✅ Bersih"
    def get_data(self): return pd.read_sql("SELECT * FROM aset_fisik", self.conn)
    def get_table_data(self, t): return pd.read_sql(f"SELECT * FROM {t}", self.conn)
    def export_ke_json(self): return pd.read_sql("SELECT * FROM aset_fisik", self.conn).to_json(orient='records')
    def import_dari_json(self, f):
        try:
            df = pd.read_json(f); self.cursor.execute("DELETE FROM aset_fisik")
            df.to_sql('aset_fisik', self.conn, if_exists='append', index=False); self.conn.commit()
            return "✅ Restore Sukses"
        except Exception as e: return str(e)
    def update_data(self, df):
        self.cursor.execute("DELETE FROM aset_fisik"); df.to_sql('aset_fisik', self.conn, if_exists='append', index=False); self.conn.commit()
