import sqlite3
import pandas as pd
import os

class IrigasiBackend:
    def __init__(self, db_path='database/irigasi.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_db()

    def init_db(self):
        """Membuat tabel database jika belum ada"""
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
                keterangan TEXT
            )
        ''')
        self.conn.commit()

    def import_data_lama(self, folder_path):
        """Membaca file CSV/XLS lama dan memasukkan ke DB"""
        files = os.listdir(folder_path)
        count = 0
        
        for file in files:
            file_path = os.path.join(folder_path, file)
            # Deteksi jenis aset dari nama file
            jenis = "Umum"
            if "bendung" in file.lower(): jenis = "Bendung"
            elif "saluran" in file.lower(): jenis = "Saluran"
            elif "bang_ukur" in file.lower(): jenis = "Bangunan Ukur"
            elif "terjunan" in file.lower(): jenis = "Terjunan"

            try:
                # Membaca format lama (titik koma)
                # Skiprows=1 karena biasanya baris pertama header aneh
                df = pd.read_csv(file_path, sep=';', on_bad_lines='skip', skiprows=1, header=None)
                
                for _, row in df.iterrows():
                    # Mapping kolom berdasarkan analisa file 'bendung.xls' kakak
                    # Kolom 1: Kode, Kolom 2: Nama
                    if len(row) > 3:
                        kode = str(row[1])
                        nama = str(row[2])
                        
                        self.cursor.execute('''
                            INSERT INTO aset_fisik (kode_aset, nama_aset, jenis_aset)
                            VALUES (?, ?, ?)
                        ''', (kode, nama, jenis))
                        count += 1
            except Exception as e:
                print(f"Gagal baca {file}: {e}")
        
        self.conn.commit()
        return f"Berhasil import {count} data aset baru."

    def hitung_ulang_kinerja(self):
        """Menghitung Nilai IKSI berdasarkan Permen PUPR (Logic 100/70/50)"""
        df = pd.read_sql("SELECT * FROM aset_fisik", self.conn)
        
        def rumus(row):
            total = row['kondisi_b'] + row['kondisi_rr'] + row['kondisi_rb']
            if total == 0: return 0
            # Rumus Weighted Average
            skor = (row['kondisi_b'] * 100) + (row['kondisi_rr'] * 70) + (row['kondisi_rb'] * 50)
            return round(skor / total, 2)

        df['nilai_kinerja'] = df.apply(rumus, axis=1)
        
        # Simpan balik ke database
        for _, row in df.iterrows():
            self.cursor.execute('''
                UPDATE aset_fisik SET nilai_kinerja = ? WHERE id = ?
            ''', (row['nilai_kinerja'], row['id']))
        self.conn.commit()
        return df

    def get_data(self):
        return pd.read_sql("SELECT * FROM aset_fisik", self.conn)

    def update_data(self, df_edited):
        """Update database dari hasil edit tabel di layar"""
        # Hapus data lama (simple approach) dan insert baru
        # Catatan: Di produksi, gunakan UPDATE id yang spesifik
        self.cursor.execute("DELETE FROM aset_fisik")
        df_edited.to_sql('aset_fisik', self.conn, if_exists='append', index=False)
        self.conn.commit()