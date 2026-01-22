import sqlite3
import pandas as pd
import os

class IrigasiBackend:
    def __init__(self, db_path='database/irigasi.db'):
        """
        Inisialisasi koneksi database.
        Otomatis membuat folder 'database' jika belum ada untuk mencegah error.
        """
        # --- BAGIAN PERBAIKAN ERROR ---
        folder = os.path.dirname(db_path)
        if folder and not os.path.exists(folder):
            try:
                os.makedirs(folder)
                print(f"Folder '{folder}' berhasil dibuat.")
            except OSError as e:
                print(f"Gagal membuat folder database: {e}")
        # ------------------------------

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
        """
        Membaca file CSV/XLS lama dari folder dan memasukkannya ke DB.
        """
        if not os.path.exists(folder_path):
            return f"Error: Folder '{folder_path}' tidak ditemukan."

        files = os.listdir(folder_path)
        count = 0
        errors = []
        
        for file in files:
            # Hanya proses file csv atau xls
            if not (file.endswith('.csv') or file.endswith('.xls') or file.endswith('.txt')):
                continue

            file_path = os.path.join(folder_path, file)
            
            # Deteksi jenis aset dari nama file secara sederhana
            file_lower = file.lower()
            jenis = "Umum"
            if "bendung" in file_lower: jenis = "Bendung"
            elif "saluran" in file_lower: jenis = "Saluran"
            elif "bang_ukur" in file_lower: jenis = "Bangunan Ukur"
            elif "terjunan" in file_lower: jenis = "Terjunan"
            elif "sadap" in file_lower: jenis = "Bangunan Sadap"
            elif "gorong" in file_lower: jenis = "Gorong-Gorong"
            elif "jembatan" in file_lower: jenis = "Jembatan"

            try:
                # Membaca format lama (biasanya dipisah titik koma ';')
                # Skiprows=1 karena baris pertama biasanya header teknis aneh
                df = pd.read_csv(file_path, sep=';', on_bad_lines='skip', skiprows=1, header=None, engine='python')
                
                for _, row in df.iterrows():
                    # Mapping kolom berdasarkan pola file kakak:
                    # Kolom 1 (Index 1) = Kode Aset (misal: 1-1-1-1-01)
                    # Kolom 2 (Index 2) = Nama Aset (misal: Bendung Way Seputih)
                    
                    if len(row) > 2: # Pastikan baris punya cukup kolom
                        kode = str(row[1]) if pd.notna(row[1]) else "-"
                        nama = str(row[2]) if pd.notna(row[2]) else "Tanpa Nama"
                        
                        # Bersihkan data (kadang ada karakter aneh)
                        nama = nama.strip()
                        
                        if nama and nama != "nan":
                            self.cursor.execute('''
                                INSERT INTO aset_fisik (kode_aset, nama_aset, jenis_aset)
                                VALUES (?, ?, ?)
                            ''', (kode, nama, jenis))
                            count += 1
            except Exception as e:
                errors.append(f"{file}: {str(e)}")
        
        self.conn.commit()
        
        pesan_error = ""
        if errors:
            pesan_error = f" | Gagal baca: {len(errors)} file."
            
        return f"Selesai! Berhasil import {count} aset.{pesan_error}"

    def hitung_ulang_kinerja(self):
        """
        Menghitung Nilai IKSI berdasarkan Permen PUPR.
        Logic: (B*100 + RR*70 + RB*50) / Total Volume
        """
        try:
            df = pd.read_sql("SELECT * FROM aset_fisik", self.conn)
            
            if df.empty:
                return df

            def rumus(row):
                # Pastikan angka, ganti None/NaN dengan 0
                b = float(row['kondisi_b']) if pd.notna(row['kondisi_b']) else 0
                rr = float(row['kondisi_rr']) if pd.notna(row['kondisi_rr']) else 0
                rb = float(row['kondisi_rb']) if pd.notna(row['kondisi_rb']) else 0
                
                total = b + rr + rb
                if total == 0: return 0.0
                
                # Rumus Weighted Average
                skor = (b * 100) + (rr * 70) + (rb * 50)
                return round(skor / total, 2)

            df['nilai_kinerja'] = df.apply(rumus, axis=1)
            
            # Simpan hasil hitungan balik ke database
            # Menggunakan executemany untuk performa lebih baik
            data_to_update = []
            for _, row in df.iterrows():
                data_to_update.append((row['nilai_kinerja'], row['id']))
            
            self.cursor.executemany('''
                UPDATE aset_fisik SET nilai_kinerja = ? WHERE id = ?
            ''', data_to_update)
            
            self.conn.commit()
            return df
        except Exception as e:
            print(f"Error hitung kinerja: {e}")
            return pd.DataFrame()

    def get_data(self):
        """Mengambil seluruh data untuk ditampilkan di tabel"""
        return pd.read_sql("SELECT * FROM aset_fisik", self.conn)

    def update_data(self, df_edited):
        """
        Update database dari hasil edit tabel di layar Streamlit.
        Metode: Replace All (Hapus lama, insert baru) untuk kemudahan prototype.
        """
        try:
            # Hapus data lama
            self.cursor.execute("DELETE FROM aset_fisik")
            # Masukkan data baru dari editor
            df_edited.to_sql('aset_fisik', self.conn, if_exists='append', index=False)
            self.conn.commit()
        except Exception as e:
            print(f"Error update data: {e}")

    def __del__(self):
        """Menutup koneksi saat aplikasi mati"""
        try:
            self.conn.close()
        except:
            pass
