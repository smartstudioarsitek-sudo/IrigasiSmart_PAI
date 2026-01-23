import sqlite3
import pandas as pd
import os
import json
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
        # 1. TABEL MASTER ASET (DATA STATIS - IMMUTABLE)
        # Data yang jarang berubah: Nama, Dimensi, Tahun Bangun, Koordinat
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS master_aset (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kode_aset TEXT UNIQUE, -- 9 Digit Code (Generated)
                nama_aset TEXT,
                jenis_aset TEXT,
                satuan TEXT,
                tahun_bangun INTEGER,
                dimensi_teknis TEXT, -- JSON: b, h, m, H_mercu
                luas_layanan_desain REAL, -- Area Potensial
                file_kmz TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 2. TABEL INSPEKSI BERKALA (DATA DINAMIS - HISTORY)
        # Data yang berubah tiap survei: Kondisi, Fungsi, Rekomendasi
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS inspeksi_aset (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aset_id INTEGER,
                tanggal_inspeksi DATE,
                nama_surveyor TEXT,
                
                -- KONDISI FISIK (0-100)
                kondisi_sipil REAL, 
                kondisi_me REAL,
                
                -- KINERJA FUNGSI (0-100)
                nilai_fungsi_sipil REAL, 
                nilai_fungsi_me REAL,
                
                -- ANALISA DAMPAK (Untuk Rumus Prioritas)
                luas_terdampak_aktual REAL, -- Area Service Affected
                
                rekomendasi_penanganan TEXT,
                estimasi_biaya REAL,
                
                FOREIGN KEY(aset_id) REFERENCES master_aset(id)
            )
        ''')

        # 3. TABEL DATA PENUNJANG (Tanam, P3A, SDM - Tetap)
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_tanam (id INTEGER PRIMARY KEY, musim TEXT, luas_rencana REAL, luas_realisasi REAL, debit_andalan REAL, kebutuhan_air REAL, faktor_k REAL, prod_padi REAL, prod_palawija REAL)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_p3a (id INTEGER PRIMARY KEY, nama_p3a TEXT, desa TEXT, status TEXT, keaktifan TEXT, anggota INTEGER)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_sdm_sarana (id INTEGER PRIMARY KEY, jenis TEXT, nama TEXT, kondisi TEXT, ket TEXT)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_dokumentasi (id INTEGER PRIMARY KEY, jenis_dokumen TEXT, ada INTEGER)')

        self.conn.commit()

    # --- 1. MANAJEMEN MASTER ASET (CREATE ONCE) ---
    def tambah_master_aset(self, nama, jenis, satuan, thn, luas, detail, kmz=None):
        try:
            # Generate Kode Unik Sederhana (Timestamp based for now)
            kode = f"{jenis[:3].upper()}-{int(datetime.now().timestamp())}"
            kmz_name = kmz.name if kmz else "-"
            detail_json = json.dumps(detail)
            
            self.cursor.execute('''INSERT INTO master_aset 
                (kode_aset, nama_aset, jenis_aset, satuan, tahun_bangun, dimensi_teknis, luas_layanan_desain, file_kmz)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                (kode, nama, jenis, satuan, thn, detail_json, luas, kmz_name))
            self.conn.commit()
            return "✅ Master Aset Terdaftar!"
        except Exception as e: return f"❌ Gagal: {e}"

    # --- 2. MANAJEMEN INSPEKSI (UPDATE MANY TIMES) ---
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

    # --- 3. MESIN PRIORITAS (RUMUS MATEMATIS) ---
    def get_prioritas_matematis(self):
        # Join Master + Latest Inspection
        query = '''
            SELECT m.nama_aset, m.jenis_aset, m.luas_layanan_desain, 
                   i.kondisi_sipil, i.kondisi_me, i.nilai_fungsi_sipil, i.nilai_fungsi_me, i.luas_terdampak_aktual, i.tanggal_inspeksi
            FROM master_aset m
            JOIN inspeksi_aset i ON m.id = i.aset_id
            ORDER BY i.tanggal_inspeksi DESC
        '''
        df = pd.read_sql(query, self.conn)
        # Drop duplicates to keep only latest inspection per asset
        df = df.drop_duplicates(subset=['nama_aset'])
        
        if df.empty: return df

        def hitung_skor_p(row):
            # Ambil nilai terburuk antara Sipil vs ME (Conservative approach)
            K = min(row['kondisi_sipil'], row['kondisi_me'])
            F = min(row['nilai_fungsi_sipil'], row['nilai_fungsi_me'])
            
            # Impact Factor (Rasio Luas Terdampak vs Total DI) -> Asumsi Total DI = 5000 Ha (Placeholder)
            # Semakin besar impact, semakin prioritas
            A_as = row['luas_terdampak_aktual']
            
            # FORMULA PRIORITAS PUPR (Simplifikasi Logika):
            # Prioritas = (BobotKondisi * K) + (BobotFungsi * F^1.5) * ImpactFactor
            # Kita balik logikanya: Semakin KECIL nilai K/F, semakin BESAR Prioritasnya (Skor Bahaya)
            
            bahaya_fisik = (100 - K) * 0.35
            bahaya_fungsi = (100 - F) * 1.5 * 0.65 # Fungsi dibobot lebih berat dan eksponensial
            
            skor_bahaya = (bahaya_fisik + bahaya_fungsi) * (A_as / 100) # Impact Multiplier
            
            return skor_bahaya

        df['Skor_Prioritas'] = df.apply(hitung_skor_p, axis=1)
        # Urutkan: Skor Bahaya Tertinggi di Atas
        return df.sort_values(by='Skor_Prioritas', ascending=False)

    # --- 4. DATA GETTERS ---
    def get_master_aset(self): return pd.read_sql("SELECT * FROM master_aset", self.conn)
    
    def get_history_aset(self, aset_id):
        return pd.read_sql(f"SELECT * FROM inspeksi_aset WHERE aset_id={aset_id} ORDER BY tanggal_inspeksi DESC", self.conn)

    # --- UTILS (Tetap) ---
    def hapus_semua_data(self):
        for t in ['master_aset', 'inspeksi_aset', 'data_tanam', 'data_p3a', 'data_sdm_sarana', 'data_dokumentasi']:
            self.cursor.execute(f"DELETE FROM {t}"); self.cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{t}'")
        self.conn.commit(); return "✅ Bersih"
        
    def tambah_data_tanam_lengkap(self, m, lr, lrl, qa, qb, pd, pl):
        fk = qa/qb if qb>0 else 0
        self.cursor.execute("INSERT INTO data_tanam VALUES (NULL,?,?,?,?,?,?,?,?)", (m,lr,lrl,qa,qb,round(fk,2),pd,pl))
        self.conn.commit(); return "✅ Tersimpan"
        
    def tambah_data_p3a(self, nm, ds, st, akt, ang):
        self.cursor.execute("INSERT INTO data_p3a VALUES (NULL, ?,?,?,?,?)", (nm, ds, st, akt, ang)); self.conn.commit(); return "✅ OK"
        
    def tambah_sdm_sarana(self, jns, nm, cond, ket):
        self.cursor.execute("INSERT INTO data_sdm_sarana VALUES (NULL, ?,?,?,?)", (jns, nm, cond, ket)); self.conn.commit(); return "✅ OK"
        
    def update_dokumentasi(self, d):
        self.cursor.execute("DELETE FROM data_dokumentasi")
        for k,v in d.items(): self.cursor.execute("INSERT INTO data_dokumentasi VALUES (?,?)", (k, 1 if v else 0))
        self.conn.commit(); return "✅ OK"
    
    def get_table_data(self, t): return pd.read_sql(f"SELECT * FROM {t}", self.conn)
