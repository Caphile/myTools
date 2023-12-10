from tkinter import filedialog, Tk
import chardet
import pandas as pd
import os

def filePaths():
    root = Tk()
    root.withdraw()

    fullPaths = filedialog.askopenfilenames(title = 'Select Excel File', initialdir = os.getcwd(), filetypes = [('Excel files', ('*.csv', '*.xlsx')), ("All files", "*.*")])

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

def combine():

    columns_to_keep = ['correct_response', 'response_target', 'response_time', 'relation', 'prime', 'prime_condition', 'target', 'target_condition']
    combined_df = pd.DataFrame()

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

        df = df.iloc[3 : ]  # 맨 위 3개의 레코드는 연습문제
        df = df[columns_to_keep]
        df.insert(0, 'who', name)
        df.insert(1, 'correctness', df.apply(lambda row: 1 if row['correct_response'] == row['response_target'] else 0, axis = 1))

        combined_df = pd.concat([combined_df, df], ignore_index = True)

    combined_df.to_excel('combined_data.xlsx', index = False)

if __name__ == "__main__":
    combine()