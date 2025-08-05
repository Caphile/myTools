import requests
from bs4 import BeautifulSoup

def check_remaining_classes():
    # 사당문화센터 : 3, 삼일수영장 : 7
    center_num = 7
    center = 'DONGJAK0' + str(center_num)

    base_url = 'https://sports.idongjak.or.kr/home/171'
    home_url = base_url + f'?center={center}&category1=01&category2=ALL&title=&train_day=&page='
    # 삼일수영장 / 강습수영(단체)

    page = 1

    remain_class_data = []
    indices_to_remove = {0, 5, 6, 7}
    seen_ids = set()

    while True:
        current_url = home_url + str(page)
        response = requests.get(current_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        table = soup.find('table', class_='list_lecture all_border')
        rows = table.find('tbody', class_='txtcenter').find_all('tr')

        null_check = True   # 빈 페이지 확인용
        for row in rows:
            cols = row.find_all(['td', 'th'])
            cols_text = [col.get_text(strip=True) for col in cols]

            class_id = row.get('data-classcd')
            if class_id in seen_ids:
                continue
            seen_ids.add(class_id)

            link_tag = row.find('a', href=True)
            if link_tag:
                link = link_tag['href']
                linked_url = base_url + link
                
                detail_response = requests.get(linked_url)
                detail_response.raise_for_status()
                
                detail_soup = BeautifulSoup(detail_response.text, 'html.parser')

                try:
                    info_data = detail_soup.select_one('#contents > article > div > div > div.infomation > div.info_data > dl > dd:nth-child(12)')
                    remain_cnt = info_data.get_text(separator=' ').strip()
                except:
                    info_data = detail_soup.select_one('#form_lecture_reg > fieldset > div > div.proc_read > div.infomation > div.info_data > dl > dd:nth-child(12)')
                    remain_cnt = info_data.get_text(separator=' ').strip()

                cols_text.append(f'잔여{remain_cnt}')
                cols_text.append(linked_url)
                filtered_text = [item for idx, item in enumerate(cols_text) if idx not in indices_to_remove]

            if remain_cnt != '마감':
                null_check = False
                remain_class_data.append(filtered_text)

        if null_check:
            break
        page += 1

    return remain_class_data