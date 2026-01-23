import sqlite3
import pandas as pd
import os
import json
import math
from datetime import datetime

class IrigasiBackend:
    def __init__(self, db_path='database/irigasi_enterprise.db'):
        # Pastikan folder database ada
        self.db_folder = os.path.dirname(db_path)
        if self.db_folder and not os.path.exists(self.db_folder):
            try:
                os.makedirs(self.db_folder)
            except OSError: pass

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_db()

    def init_db(self):
        # 1. Tabel Master Aset (Data Statis)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS master_aset (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kode_aset TEXT UNIQUE, 
                nama_aset TEXT,
                jenis_aset TEXT,
                satuan TEXT,
                tahun_bangun INTEGER,
                tahun_rehab_terakhir INTEGER,
                dimensi_teknis TEXT, 
                luas_layanan_desain REAL, 
                nilai_aset_baru REAL DEFAULT 0,
                file_kmz TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 2. Tabel Inspeksi (Data Dinamis)
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
                foto_bukti TEXT,
                FOREIGN KEY(aset_id) REFERENCES master_aset(id)
            )
        ''')

        # 3. Tabel Penunjang
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_tanam (id INTEGER PRIMARY KEY, musim TEXT, luas_rencana REAL, luas_realisasi REAL, debit_andalan REAL, kebutuhan_air REAL, faktor_k REAL, prod_padi REAL, prod_palawija REAL)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_p3a (id INTEGER PRIMARY KEY, nama_p3a TEXT, desa TEXT, status TEXT, keaktifan TEXT, anggota INTEGER)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_sdm_sarana (id INTEGER PRIMARY KEY, jenis TEXT, nama TEXT, kondisi TEXT, ket TEXT)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS data_dokumentasi (id INTEGER PRIMARY KEY, jenis_dokumen TEXT, ada INTEGER)')

        # Auto-Repair Kolom (Jika tabel lama masih ada)
        try:
            self.cursor.execute("ALTER TABLE master_aset ADD COLUMN nilai_aset_baru REAL DEFAULT 0")
        except: pass
        try:
            self.cursor.execute("ALTER TABLE master_aset ADD COLUMN tahun_rehab_terakhir INTEGER DEFAULT 0")
        except: pass
        
        self.conn.commit()

    # --- FITUR BACKUP & RESTORE (INI YANG TADI ERROR) ---
    def export_ke_json(self):
        """Backup SEMUA tabel ke satu JSON"""
        data = {}
        try:
            data['master_aset'] = pd.read_sql("SELECT * FROM master_aset", self.conn).to_dict(orient='records')
            data['inspeksi_aset'] = pd.read_sql("SELECT * FROM inspeksi_aset", self.conn).to_dict(orient='records')
            data['data_tanam'] = pd.read_sql("SELECT * FROM data_tanam", self.conn).to_dict(orient='records')
            data['data_p3a'] = pd.read_sql("SELECT * FROM data_p3a", self.conn).to_dict(orient='records')
            data['data_sdm_sarana'] = pd.read_sql("SELECT * FROM data_sdm_sarana", self.conn).to_dict(orient='records')
            data['data_dokumentasi'] = pd.read_sql("SELECT * FROM data_dokumentasi", self.conn).to_dict(orient='records')
            return json.dumps(data, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def import_dari_json(self, json_file):
        """Restore database dari file JSON lengkap"""
        try:
            data = json.load(json_file)
            
            # Hapus data lama (Reset)
            self.hapus_semua_data()
            
            # Insert data baru
            if 'master_aset' in data and data['master_aset']:
                pd.DataFrame(data['master_aset']).to_sql('master_aset', self.conn, if_exists='append', index=False)
            
            if 'inspeksi_aset' in data and data['inspeksi_aset']:
                pd.DataFrame(data['inspeksi_aset']).to_sql('inspeksi_aset', self.conn, if_exists='append', index=False)
                
            if 'data_tanam' in data and data['data_tanam']:
                pd.DataFrame(data['data_tanam']).to_sql('data_tanam', self.conn, if_exists='append', index=False)
                
            if 'data_p3a' in data and data['data_p3a']:
                pd.DataFrame(data['data_p3a']).to_sql('data_p3a', self.conn, if_exists='append', index=False)
                
            if 'data_sdm_sarana' in data and data['data_sdm_sarana']:
                pd.DataFrame(data['data_sdm_sarana']).to_sql('data_sdm_sarana', self.conn, if_exists='append', index=False)
                
            if 'data_dokumentasi' in data and data['data_dokumentasi']:
                pd.DataFrame(data['data_dokumentasi']).to_sql('data_dokumentasi', self.conn, if_exists='append', index=False)
                
            self.conn.commit()
            return "✅ Restore Berhasil! Semua data kembali."
        except Exception as e:
            return f"❌ Gagal Restore: {e}"

    # --- CRUD MASTER ASET ---
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
            return "✅ Master Aset Terdaftar!"
        except Exception as e: return f"❌ Gagal: {e}"

    # --- CRUD INSPEKSI ---
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

    # --- MESIN PRIORITAS ---
    def get_prioritas_matematis(self):
        query = '''
            SELECT m.nama_aset, m.jenis_aset, m.luas_layanan_desain, m.nilai_aset_baru,
                   i.kondisi_sipil, i.kondisi_me, i.nilai_fungsi_sipil, i.nilai_fungsi_me, 
                   i.luas_terdampak_aktual, i.estimasi_biaya
            FROM master_aset m
            JOIN inspeksi_aset i ON m.id = i.aset_id
            ORDER BY i.tanggal_inspeksi DESC
        '''
        try:
            df = pd.read_sql(query, self.conn)
            df = df.drop_duplicates(subset=['nama_aset'])
            
            if df.empty: return df

            def hitung_skor_urgensi(row):
                K = min(row['kondisi_sipil'], row['kondisi_me']) 
                F = min(row['nilai_fungsi_sipil'], row['nilai_fungsi_me'])
                A_as = row['luas_terdampak_aktual']
                Impact_Factor = math.log10(A_as + 1) if A_as > 0 else 0
                
                Kerusakan_Fisik = (100 - K) * 0.4
                Kegagalan_Fungsi = (100 - F) * 1.5 * 0.6
                
                return (Kerusakan_Fisik + Kegagalan_Fungsi) * Impact_Factor

            df['Skor_Prioritas'] = df.apply(hitung_skor_urgensi, axis=1)
            
            def label_prioritas(skor):
                if skor > 200: return "1. DARURAT (Segera)"
                if skor > 100: return "2. MENDESAK (Thn Depan)"
                if skor > 50: return "3. PERLU PERHATIAN"
                return "4. RUTIN"
                
            df['Kelas_Prioritas'] = df['Skor_Prioritas'].apply(label_prioritas)
            return df.sort_values(by='Skor_Prioritas', ascending=False)
        except:
            return pd.DataFrame() # Return kosong jika error

    # --- HITUNG IKSI ---
    def hitung_iksi_lengkap(self):
        prioritas = self.get_prioritas_matematis()
        skor_fisik = 0
        if not prioritas.empty:
            total_area = prioritas['luas_terdampak_aktual'].sum()
            if total_area > 0:
                prioritas['nilai_gabungan'] = (prioritas[['kondisi_sipil', 'kondisi_me']].min(axis=1) + 
                                             prioritas[['nilai_fungsi_sipil', 'nilai_fungsi_me']].min(axis=1)) / 2
                skor_fisik = (prioritas['nilai_gabungan'] * prioritas['luas_terdampak_aktual']).sum() / total_area
            else:
                skor_fisik = 60

        df_tanam = pd.read_sql("SELECT * FROM data_tanam", self.conn)
        skor_tanam = 0
        if not df_tanam.empty:
            def calc_tanam(r):
                nk = 100 if r['faktor_k'] >= 1 else (80 if r['faktor_k']>=0.7 else 60)
                return nk
            skor_tanam = df_tanam.apply(calc_tanam, axis=1).mean()

        skor_sarana = 60 
        skor_sdm = 60
        skor_dok = 60
        skor_p3a = 60
        
        total_iksi = (skor_fisik * 0.45) + (skor_tanam * 0.15) + (skor_sarana * 0.10) + \
                     (skor_sdm * 0.15) + (skor_dok * 0.05) + (skor_p3a * 0.10)
        
        return total_iksi, skor_fisik, skor_tanam

    # --- UTILS LAINNYA ---
    def hapus_semua_data(self):
        for t in ['master_aset','inspeksi_aset','data_tanam','data_p3a','data_sdm_sarana','data_dokumentasi']:
            try:
                self.cursor.execute(f"DELETE FROM {t}")
                self.cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{t}'")
            except: pass
        self.conn.commit()
        return "✅ Database Bersih"
        
    def get_master_aset(self): return pd.read_sql("SELECT * FROM master_aset", self.conn)
    def get_table_data(self, t): return pd.read_sql(f"SELECT * FROM {t}", self.conn)
    def tambah_data_tanam_lengkap(self, m, lr, lrl, qa, qb, pd, pl):
        fk = qa/qb if qb>0 else 0
        self.cursor.execute("INSERT INTO data_tanam VALUES (NULL,?,?,?,?,?,?,?,?)", (m,lr,lrl,qa,qb,round(fk,2),pd,pl)); self.conn.commit(); return "✅ OK"
    def tambah_data_p3a(self, nm, ds, st, akt, ang): self.cursor.execute("INSERT INTO data_p3a VALUES (NULL,?,?,?,?,?)", (nm,ds,st,akt,ang)); self.conn.commit(); return "✅ OK"
    def tambah_sdm_sarana(self, jns, nm, cond, ket): self.cursor.execute("INSERT INTO data_sdm_sarana VALUES (NULL,?,?,?,?)", (jns,nm,cond,ket)); self.conn.commit(); return "✅ OK"
    def update_dokumentasi(self, d):
        self.cursor.execute("DELETE FROM data_dokumentasi"); [self.cursor.execute("INSERT INTO data_dokumentasi VALUES (?,?)", (k,1 if v else 0)) for k,v in d.items()]; self.conn.commit(); return "✅ OK"
