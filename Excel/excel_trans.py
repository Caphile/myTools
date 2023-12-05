from tkinter import filedialog, Tk
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

def trans():
    paths, names = filePaths()
    for path, name in zip(paths, names):
        if name.endswith('.csv'):
            df = pd.read_csv(os.path.join(path, name))
        elif name.endswith('.xlsx'):
            df = pd.read_excel(os.path.join(path, name))
        else:
            print(f"Unsupported file type: {name}")
            continue

        base, ext = os.path.splitext(name)
        new_name = f"{base}_ansi{ext}"
        df.to_csv(os.path.join(path, new_name), encoding = 'ansi', index = False)

if __name__ == "__main__":
    trans()