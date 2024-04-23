import zipfile
import os

def unzip_file(zip_file, extract_dir):
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

extract_dir = "/home/maglev/.magshell"

zip_file = "DNA_Analyzer_Code-main2.zip"

unzip_file(zip_file, extract_dir)
