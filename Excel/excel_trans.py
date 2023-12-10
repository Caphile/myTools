from tkinter import filedialog, Tk
import chardet
import pandas as pd
import os

def filePaths():
    root = Tk()
    root.withdraw()

    fullPaths = filedialog.askopenfilenames(title = 'Select Excel File', initialdir = os.getcwd(), filetypes=[('Excel files', ('*.csv', '*.xlsx')), ("All files", "*.*")])

    paths, names = [], []
    for p in fullPaths:
        temp = p.split('/')
        paths.append('/'.join(temp[ : -1]))
        names.append(temp[-1])
    
    return paths, names

def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read())
    return result['encoding']

def trans():
    paths, names = filePaths()
    for path, name in zip(paths, names):
        if name.endswith('.csv'):
            encoding = detect_encoding(os.path.join(path, name))
            df = pd.read_csv(os.path.join(path, name), encoding = encoding)
        elif name.endswith('.xlsx'):
            encoding = detect_encoding(os.path.join(path, name))
            df = pd.read_excel(os.path.join(path, name), encoding = encoding)
        else:
            print(f"Unsupported file type: {name}")
            continue

        base, ext = os.path.splitext(name)
        new_name = f"{base}_ansi{ext}"
        df.to_csv(os.path.join(path, new_name), encoding = 'ansi', index = False)

if __name__ == "__main__":
    trans()