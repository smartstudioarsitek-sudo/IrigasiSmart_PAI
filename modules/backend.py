import sqlite3
import pandas as pd
import os

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
        """
        Membuat tabel dan OTOMATIS MEMPERBAIKI jika ada kolom yang kurang (Auto-Migration).
        """
        # 1. Buat tabel dasar jika belum ada
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
        
        # 2. Cek apakah kolom 'file_kmz' sudah ada?
        # Ini solusi untuk error "no column named file_kmz"
        cek_kolom = self.cursor.execute("PRAGMA table_info(aset_fisik)").fetchall()
        list_kolom = [kol[1] for kol in cek_kolom]
        
        if 'file_kmz' not in list_kolom:
            print("⚙️ Sedang memperbarui database: Menambahkan kolom file_kmz...")
            try:
                self.cursor.execute("ALTER TABLE aset_fisik ADD COLUMN file_kmz TEXT")
                self.conn.commit()
            except Exception as e:
                print(f"Gagal tambah kolom: {e}")

    def tambah_data_baru(self, nama, jenis, satuan, b, rr, rb, file_kmz=None):
        try:
            total = b + rr + rb
            nilai = 0
            if total > 0:
                nilai = ((b * 100) + (rr * 70) + (rb * 50)) / total
            
            # Ambil nama file saja (saat ini fitur baru sebatas simpan file)
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
        if not os.path.exists(folder_path):
            # Fallback check
            current_dir = os.getcwd()
            alt_path = os.path.join(current_dir, folder_path)
            if os.path.exists(alt_path):
                folder_path = alt_path
            else:
                return "❌ Folder data_lama tidak ditemukan."

        files = os.listdir(folder_path)
        count = 0
        
        for file in files:
            if not (file.endswith('.csv') or file.endswith('.xls')): continue
            file_path = os.path.join(folder_path, file)
            
            # Deteksi jenis sederhana
            jenis = "Umum"
            if "bendung" in file.lower(): jenis = "Bendung"
            elif "saluran" in file.lower(): jenis = "Saluran"

            try:
                df = pd.read_csv(file_path, sep=';', on_bad_lines='skip', skiprows=0, header=None, engine='python')
                for _, row in df.iterrows():
                    if len(row) > 2:
                        kode = str(row[1]).strip()
                        nama = str(row[2]).strip()
                        if len(kode) > 3 and nama.lower() != 'nan':
                            # Cek duplikat
                            cek = self.cursor.execute("SELECT id FROM aset_fisik WHERE kode_aset = ?", (kode,)).fetchone()
                            if not cek:
                                self.cursor.execute('''
                                    INSERT INTO aset_fisik (kode_aset, nama_aset, jenis_aset)
                                    VALUES (?, ?, ?)
                                ''', (kode, nama, jenis))
                                count += 1
            except: pass
        
        self.conn.commit()
        return f"✅ Import Selesai. {count} aset baru ditambahkan."

    def hitung_ulang_kinerja(self):
        df = pd.read_sql("SELECT * FROM aset_fisik", self.conn)
        if df.empty: return df

        def rumus(row):
            b = float(row['kondisi_b']) if pd.notna(row['kondisi_b']) else 0
            rr = float(row['kondisi_rr']) if pd.notna(row['kondisi_rr']) else 0
            rb = float(row['kondisi_rb']) if pd.notna(row['kondisi_rb']) else 0
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
        try:
            self.cursor.execute("DELETE FROM aset_fisik")
            df_edited.to_sql('aset_fisik', self.conn, if_exists='append', index=False)
            self.conn.commit()
        except Exception as e:
            print(f"Gagal update: {e}")
