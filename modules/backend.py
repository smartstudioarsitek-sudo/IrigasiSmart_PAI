import sqlite3
import pandas as pd
import os
import json
import math
from datetime import datetime

class IrigasiBackend:
    def __init__(self, db_path='database/irigasi_enterprise.db'):
        self.db_folder = os.path.dirname(db_path)
        if self.db_folder and not os.path.exists(self.db_folder):
            try:
                os.makedirs(self.db_folder)
            except OSError: pass

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_db()

    def init_db(self):
        # 1. TABEL MASTER ASET (DATA STATIS + VALUASI)
        # Sesuai Lampiran I Permen 23/2015
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS master_aset (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kode_aset TEXT UNIQUE, 
                nama_aset TEXT,
                jenis_aset TEXT,
                satuan TEXT,
                tahun_bangun INTEGER,
                tahun_rehab_terakhir INTEGER, -- Kolom Baru: Sejarah Rehab
                dimensi_teknis TEXT, 
                luas_layanan_desain REAL, 
                nilai_aset_baru REAL DEFAULT 0, -- Kolom Baru: Valuasi (NAB)
                file_kmz TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 2. TABEL INSPEKSI BERKALA (DATA DINAMIS)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS inspeksi_aset (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aset_id INTEGER,
                tanggal_inspeksi DATE,
                nama_surveyor TEXT,
                kondisi_sipil REAL, 
                kondisi_me REAL,
                nilai_fungsi_sipil REAL, 
                nilai_fungsi_me REAL,
                luas_terdampak_aktual REAL,
                rekomendasi_penanganan TEXT,
                estimasi_biaya REAL,
                foto_bukti TEXT, -- Path foto (Placeholder)
                FOREIGN KEY(aset_id) REFERENCES master_aset(id)
            )
        ''')

        # 3. TABEL DATA PENUNJANG (Tanam, P3A, SDM, Dokumen)
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_tanam (id INTEGER PRIMARY KEY, musim TEXT, luas_rencana REAL, luas_realisasi REAL, debit_andalan REAL, kebutuhan_air REAL, faktor_k REAL, prod_padi REAL, prod_palawija REAL)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_p3a (id INTEGER PRIMARY KEY, nama_p3a TEXT, desa TEXT, status TEXT, keaktifan TEXT, anggota INTEGER)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_sdm_sarana (id INTEGER PRIMARY KEY, jenis TEXT, nama TEXT, kondisi TEXT, ket TEXT)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_dokumentasi (id INTEGER PRIMARY KEY, jenis_dokumen TEXT, ada INTEGER)')

        # Auto-Migration (Safety Check)
        cek = self.cursor.execute("PRAGMA table_info(master_aset)").fetchall()
        cols = [c[1] for c in cek]
        if 'nilai_aset_baru' not in cols: self.cursor.execute("ALTER TABLE master_aset ADD COLUMN nilai_aset_baru REAL DEFAULT 0")
        if 'tahun_rehab_terakhir' not in cols: self.cursor.execute("ALTER TABLE master_aset ADD COLUMN tahun_rehab_terakhir INTEGER DEFAULT 0")
        self.conn.commit()

    # --- 1. MANAJEMEN MASTER (DENGAN VALUASI) ---
    def tambah_master_aset(self, nama, jenis, satuan, thn_bangun, thn_rehab, luas, nab, detail, kmz=None):
        try:
            kode = f"{jenis[:3].upper()}-{int(datetime.now().timestamp())}"
            kmz_name = kmz.name if kmz else "-"
            detail_json = json.dumps(detail)
            
            self.cursor.execute('''INSERT INTO master_aset 
                (kode_aset, nama_aset, jenis_aset, satuan, tahun_bangun, tahun_rehab_terakhir, luas_layanan_desain, nilai_aset_baru, dimensi_teknis, file_kmz)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (kode, nama, jenis, satuan, thn_bangun, thn_rehab, luas, nab, detail_json, kmz_name))
            self.conn.commit()
            return "✅ Master Aset Terdaftar (Lengkap dengan Valuasi)!"
        except Exception as e: return f"❌ Gagal: {e}"

    # --- 2. MANAJEMEN INSPEKSI ---
    def tambah_inspeksi(self, aset_id, surveyor, ks, kme, fs, fme, luas_impact, rek, biaya):
        try:
            tgl = datetime.now().strftime("%Y-%m-%d")
            self.cursor.execute('''INSERT INTO inspeksi_aset
                (aset_id, tanggal_inspeksi, nama_surveyor, kondisi_sipil, kondisi_me, nilai_fungsi_sipil, nilai_fungsi_me, luas_terdampak_aktual, rekomendasi_penanganan, estimasi_biaya)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (aset_id, tgl, surveyor, ks, kme, fs, fme, luas_impact, rek, biaya))
            self.conn.commit()
            return "✅ Laporan Inspeksi Disimpan!"
        except Exception as e: return f"❌ Gagal: {e}"

    # --- 3. MESIN PRIORITAS (RUMUS MATEMATIS PERMEN PUPR) ---
    def get_prioritas_matematis(self):
        query = '''
            SELECT m.nama_aset, m.jenis_aset, m.luas_layanan_desain, m.nilai_aset_baru,
                   i.kondisi_sipil, i.kondisi_me, i.nilai_fungsi_sipil, i.nilai_fungsi_me, 
                   i.luas_terdampak_aktual, i.estimasi_biaya
            FROM master_aset m
            JOIN inspeksi_aset i ON m.id = i.aset_id
            ORDER BY i.tanggal_inspeksi DESC
        '''
        df = pd.read_sql(query, self.conn)
        df = df.drop_duplicates(subset=['nama_aset'])
        
        if df.empty: return df

        def hitung_skor_urgensi(row):
            # 1. Tentukan Nilai K (Kondisi) dan F (Fungsi) Terburuk
            # Kita ambil nilai minimum antara Sipil & ME sebagai 'Bottleneck'
            K = min(row['kondisi_sipil'], row['kondisi_me']) 
            F = min(row['nilai_fungsi_sipil'], row['nilai_fungsi_me'])
            
            # 2. Faktor Dampak (Impact Factor)
            # Aset dengan area layanan besar harus prioritas
            # Kita gunakan Logaritma Luas agar skala 1000ha vs 100ha tidak terlalu timpang tapi tetap signifikan
            A_as = row['luas_terdampak_aktual']
            Impact_Factor = math.log10(A_as + 1) if A_as > 0 else 0
            
            # 3. RUMUS PRIORITAS (URGENSI)
            # P = (Tingkat Kerusakan Fisik + Tingkat Kegagalan Fungsi^1.5) * Impact
            # (100-K) = Kerusakan. (100-F) = Kegagalan Fungsi.
            
            Kerusakan_Fisik = (100 - K) * 0.4  # Bobot 40%
            Kegagalan_Fungsi = (100 - F) * 1.5 * 0.6 # Bobot 60% & Eksponensial (Fungsi lebih mematikan)
            
            Skor_Bahaya = (Kerusakan_Fisik + Kegagalan_Fungsi) * Impact_Factor
            return Skor_Bahaya

        df['Skor_Prioritas'] = df.apply(hitung_skor_urgensi, axis=1)
        
        # Tambahkan Label Prioritas
        def label_prioritas(skor):
            # Threshold ini relatif, bisa disesuaikan dengan data lapangan
            if skor > 200: return "1. DARURAT (Segera)"
            if skor > 100: return "2. MENDESAK (Tahun Depan)"
            if skor > 50: return "3. PERLU PERHATIAN"
            return "4. RUTIN"
            
        df['Kelas_Prioritas'] = df['Skor_Prioritas'].apply(label_prioritas)
        return df.sort_values(by='Skor_Prioritas', ascending=False)

    # --- 4. HITUNG IKSI AUDIT (6 PILAR) ---
    def hitung_iksi_lengkap(self):
        # A. FISIK (45%)
        prioritas = self.get_prioritas_matematis()
        skor_fisik = 0
        if not prioritas.empty:
            # Weighted average by area
            total_area = prioritas['luas_terdampak_aktual'].sum()
            if total_area > 0:
                # Nilai Aset Gabungan = Rata-rata Kondisi & Fungsi
                prioritas['nilai_gabungan'] = (prioritas[['kondisi_sipil', 'kondisi_me']].min(axis=1) + 
                                             prioritas[['nilai_fungsi_sipil', 'nilai_fungsi_me']].min(axis=1)) / 2
                skor_fisik = (prioritas['nilai_gabungan'] * prioritas['luas_terdampak_aktual']).sum() / total_area
            else:
                skor_fisik = 60 # Default

        # B. TANAM (15%) - FAKTOR K
        df_tanam = pd.read_sql("SELECT * FROM data_tanam", self.conn)
        skor_tanam = 0
        if not df_tanam.empty:
            def calc_tanam(r):
                nk = 100 if r['faktor_k'] >= 1 else (80 if r['faktor_k']>=0.7 else 60)
                return nk # Simplifikasi fokus ke Faktor K
            skor_tanam = df_tanam.apply(calc_tanam, axis=1).mean()

        # C. NON-FISIK LAINNYA (Placeholder Logic - Harus diisi user)
        # Asumsi default Cukup (60) jika data kosong
        skor_sarana = 60 
        skor_sdm = 60
        skor_dok = 60
        skor_p3a = 60
        
        total_iksi = (skor_fisik * 0.45) + (skor_tanam * 0.15) + (skor_sarana * 0.10) + \
                     (skor_sdm * 0.15) + (skor_dok * 0.05) + (skor_p3a * 0.10)
        
        return total_iksi, skor_fisik, skor_tanam

    # --- UTILS (CRUD Non-Fisik dll) ---
    # (Kode utilitas sama seperti sebelumnya, dipertahankan)
    def hapus_semua_data(self):
        for t in ['master_aset', 'inspeksi_aset', 'data_tanam', 'data_p3a', 'data_sdm_sarana', 'data_dokumentasi']:
            self.cursor.execute(f"DELETE FROM {t}"); self.cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{t}'")
        self.conn.commit(); return "✅ Bersih"
    def get_master_aset(self): return pd.read_sql("SELECT * FROM master_aset", self.conn)
    def get_table_data(self, t): return pd.read_sql(f"SELECT * FROM {t}", self.conn)
    def export_ke_json(self): return pd.read_sql("SELECT * FROM master_aset", self.conn).to_json(orient='records')
    def import_dari_json(self, f):
        try: df = pd.read_json(f); self.cursor.execute("DELETE FROM master_aset"); df.to_sql('master_aset', self.conn, if_exists='append', index=False); self.conn.commit(); return "✅ OK"
        except Exception as e: return str(e)
    def tambah_data_tanam_lengkap(self, m, lr, lrl, qa, qb, pd, pl):
        fk = qa/qb if qb>0 else 0
        self.cursor.execute("INSERT INTO data_tanam VALUES (NULL,?,?,?,?,?,?,?,?)", (m,lr,lrl,qa,qb,round(fk,2),pd,pl)); self.conn.commit(); return "✅ OK"
    def tambah_data_p3a(self, nm, ds, st, akt, ang): self.cursor.execute("INSERT INTO data_p3a VALUES (NULL,?,?,?,?,?)", (nm,ds,st,akt,ang)); self.conn.commit(); return "✅ OK"
    def tambah_sdm_sarana(self, jns, nm, cond, ket): self.cursor.execute("INSERT INTO data_sdm_sarana VALUES (NULL,?,?,?,?)", (jns,nm,cond,ket)); self.conn.commit(); return "✅ OK"
    def update_dokumentasi(self, d):
        self.cursor.execute("DELETE FROM data_dokumentasi"); [self.cursor.execute("INSERT INTO data_dokumentasi VALUES (?,?)", (k,1 if v else 0)) for k,v in d.items()]; self.conn.commit(); return "✅ OK"
