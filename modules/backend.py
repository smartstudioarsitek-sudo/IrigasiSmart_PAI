import sqlite3
import pandas as pd
import os

class IrigasiBackend:
    def __init__(self, db_path='database/irigasi.db'):
        """
        Inisialisasi koneksi database.
        Otomatis membuat folder 'database' jika belum ada.
        """
        # --- PERBAIKAN: AUTO-CREATE FOLDER ---
        self.db_folder = os.path.dirname(db_path)
        if self.db_folder and not os.path.exists(self.db_folder):
            try:
                os.makedirs(self.db_folder)
            except OSError as e:
                print(f"Error membuat folder DB: {e}")

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
        Import data robust: Menangani format file legacy yang campur aduk.
        """
        # Cek apakah folder ada
        if not os.path.exists(folder_path):
            # Coba cari folder relatif terhadap script yang jalan
            current_dir = os.getcwd()
            alt_path = os.path.join(current_dir, folder_path)
            if os.path.exists(alt_path):
                folder_path = alt_path
            else:
                return f"❌ ERROR: Folder '{folder_path}' tidak ditemukan di server. Pastikan folder 'data_lama' sudah di-upload ke GitHub."

        files = os.listdir(folder_path)
        count_sukses = 0
        files_processed = 0
        errors = []
        
        for file in files:
            # Filter file sampah/hidden
            if file.startswith('.') or not (file.endswith('.csv') or file.endswith('.xls') or file.endswith('.txt')):
                continue

            files_processed += 1
            file_path = os.path.join(folder_path, file)
            
            # Deteksi jenis aset dari nama file
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
                # --- LOGIKA BACA FILE YANG LEBIH KUAT ---
                # File kakak rata-rata adalah CSV dengan pemisah titik koma (;), 
                # meskipun ekstensinya .xls
                try:
                    # Coba baca sebagai CSV (titik koma)
                    df = pd.read_csv(file_path, sep=';', on_bad_lines='skip', skiprows=0, header=None, engine='python')
                except:
                    # Jika gagal, coba baca sebagai Excel beneran
                    try:
                        df = pd.read_excel(file_path, header=None)
                    except:
                        # Skip file ini jika tidak bisa dibaca sama sekali
                        continue

                # Loop setiap baris
                for _, row in df.iterrows():
                    # Kriteria Data Valid Ala File Lama Kakak:
                    # Minimal punya 3 kolom
                    if len(row) < 3: 
                        continue
                    
                    kode = str(row[1]).strip()
                    nama = str(row[2]).strip()

                    # Validasi: Kode biasanya ada angkanya, Nama tidak boleh kosong/NaN
                    if (len(kode) > 3) and (nama.lower() != 'nan') and (nama != ''):
                        # Cek duplikat agar tidak double saat import berkali-kali
                        cek = self.cursor.execute("SELECT id FROM aset_fisik WHERE kode_aset = ?", (kode,)).fetchone()
                        
                        if not cek:
                            self.cursor.execute('''
                                INSERT INTO aset_fisik (kode_aset, nama_aset, jenis_aset)
                                VALUES (?, ?, ?)
                            ''', (kode, nama, jenis))
                            count_sukses += 1
                            
            except Exception as e:
                errors.append(f"{file}: {str(e)}")
        
        self.conn.commit()
        
        pesan_error = ""
        if errors:
            pesan_error = f"\n⚠️ Ada {len(errors)} file bermasalah."
            
        if files_processed == 0:
            return "⚠️ Folder ditemukan TAPI tidak ada file .xls/.csv di dalamnya. Pastikan file sudah di-upload."
            
        return f"✅ SUKSES! {count_sukses} aset baru berhasil di-import dari {files_processed} file.{pesan_error}"

    def hitung_ulang_kinerja(self):
        """
        Menghitung Nilai IKSI berdasarkan Permen PUPR.
        Rumus: (B*100 + RR*70 + RB*50) / Total Volume
        """
        try:
            df = pd.read_sql("SELECT * FROM aset_fisik", self.conn)
            
            if df.empty:
                return df

            def rumus(row):
                # Konversi ke float & handle error jika kosong
                try:
                    b = float(row['kondisi_b']) if pd.notna(row['kondisi_b']) else 0
                    rr = float(row['kondisi_rr']) if pd.notna(row['kondisi_rr']) else 0
                    rb = float(row['kondisi_rb']) if pd.notna(row['kondisi_rb']) else 0
                except:
                    return 0

                total = b + rr + rb
                if total == 0: return 0.0
                
                # --- RUMUS INTI SESUAI PERMINTAAN KAKAK ---
                # Baik = 100%, RR = 70%, RB = 50%
                skor = (b * 100) + (rr * 70) + (rb * 50)
                
                return round(skor / total, 2)

            df['nilai_kinerja'] = df.apply(rumus, axis=1)
            
            # Update massal ke database
            data_to_update = []
            for _, row in df.iterrows():
                data_to_update.append((row['nilai_kinerja'], row['id']))
            
            self.cursor.executemany('UPDATE aset_fisik SET nilai_kinerja = ? WHERE id = ?', data_to_update)
            self.conn.commit()
            return df
            
        except Exception as e:
            print(f"Error hitung: {e}")
            return pd.DataFrame() # Return kosong jika error

    def get_data(self):
        return pd.read_sql("SELECT * FROM aset_fisik", self.conn)

    def update_data(self, df_edited):
        """Update data dari tabel editor"""
        try:
            # Cara aman: Hapus semua -> Insert ulang (untuk prototype)
            # Untuk production sebaiknya UPDATE per ID
            self.cursor.execute("DELETE FROM aset_fisik")
            df_edited.to_sql('aset_fisik', self.conn, if_exists='append', index=False)
            self.conn.commit()
        except Exception as e:
            print(f"Gagal update: {e}")
