# -*- coding: cp949 -*-

import os, re
import shutil

root_path = 'C:/Nexon/Maple'
pattern = r'\d{6}'

jpg_files = [os.path.join(root, name) for root, dirs, files in os.walk(".")
             for name in files if name.endswith(".jpg")]

for jpg_name in os.listdir(root_path):
    if (jpg_name.startswith("Maple_A_") or jpg_name.startswith("Maple_")) and jpg_name.endswith(".jpg"):
        date = re.search(pattern, jpg_name).group()

        year = f'20{date[0 : 2]}'
        month = f'{date[2 : 4]}'.zfill(2)
        day = f'{date[4 : 6]}'.zfill(2)

        new_path = f'{root_path}/Screenshots/'

        new_path += f'/{year}년'
        if not os.path.exists(new_path):
            os.mkdir(new_path)

        new_path += f'/{month}월'
        if not os.path.exists(new_path):
            os.mkdir(new_path)

        new_path += f'/{day}일'
        if not os.path.exists(new_path):
            os.mkdir(new_path)

        shutil.move(f'{root_path}/{jpg_name}', f'{new_path}/{jpg_name}')