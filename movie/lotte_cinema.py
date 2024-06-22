import time, re

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

import matplotlib.pyplot as plt

from datetime import datetime, timedelta
from matplotlib.dates import HourLocator, DateFormatter

import cinema_list as CL

def extract(cinemaID, day):
    # options
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    # options.add_argument("headless")

    driver = webdriver.Chrome(service=service, options=options)

    wait = WebDriverWait(driver, 10)

    url = 'https://www.lottecinema.co.kr/NLCHS/Cinema/Detail?divisionCode=1&detailDivisionCode=1&cinemaID=' + str(cinemaID)
    driver.get(url)

    closebanner = wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[20]/div[3]/button')))
    closebanner.click()

    daypath = f'/html/body/div[9]/ul/li[1]/div/div[1]/div/ul/div[1]/div/div[{1 + day}]/li/a'
    dayselect = wait.until(EC.element_to_be_clickable((By.XPATH, daypath)))
    dayselect.click()

    time.sleep(1)
    contents = driver.find_element(By.XPATH, '/html/body/div[9]/ul/li[1]/div/div[3]')
    soup = BeautifulSoup(contents.get_attribute('outerHTML'), 'html.parser')

    movies = []
    movie_elements = soup.find_all('div', class_='time_select_wrap')
    for movie_element in movie_elements:
        title = movie_element.find('p').text.strip()                                # 영화제목
        showings = []
        showing_elements = movie_element.find_all('ul', class_='list_time')
        for showing_element in showing_elements:
            for li in showing_element.find_all('li'):
                showing_time = li.find('strong').text.strip()                       # 시작시간
                tooltip = li.find('div', class_='tooltip').text.strip()
                end_time = tooltip.split(' ')[1]                                    # 종료시간
                remaining_seats = li.find('dd', class_='seat').strong.text.strip()  # 잔여좌석
                hall = li.find('dd', class_='hall').text.strip()                    # 상영관
                showings.append({'time': showing_time, 'end_time': end_time, 'remaining_seats': remaining_seats, 'hall': hall})

        movie_info = {'title': title, 'showings': showings}
        movies.append(movie_info)

    driver.quit()
    return movies

def visualize_movie_schedule(movies, cinema, day=0):
    def clear_overnight(time_str):
        if int(time_str.split(':')[0]) >= 24:
            hour = int(time_str.split(':')[0]) - 24
            minute = time_str.split(':')[1]
            time_str = f'{hour:02d}:{minute}'
            time = datetime.strptime(time_str, '%H:%M') + timedelta(days=1)
        else:
            time = datetime.strptime(time_str, '%H:%M')
        return time
    
    plt.rcParams['font.family'] = 'Malgun Gothic'
    fig, ax = plt.subplots(figsize=(12, 8))
    colors = plt.cm.tab20.colors + plt.cm.tab20b.colors + plt.cm.tab20c.colors

    def extract_number(hall_name):
        match = re.search(r'(\d+)', hall_name)
        return int(match.group()) if match else float('inf')

    hall_names = sorted(set(showing['hall'] for movie in movies for showing in movie['showings']), key=extract_number)
    hall_count = len(hall_names)

    for idx, movie in enumerate(movies):
        for showing in movie['showings']:
            start_time_str = showing['time']
            end_time_str = showing['end_time']
            hall = showing['hall']

            start_time = clear_overnight(start_time_str)
            end_time = clear_overnight(end_time_str)

            hall_index = hall_names.index(hall)
            ax.plot([start_time, end_time], [hall_index, hall_index], marker='o', color=colors[idx])
            ax.text(start_time, hall_index, f"{showing['time']} - {showing['end_time']}\n{movie['title']}", fontsize=8, va='bottom', ha='left')

    current_date = datetime.now()
    target_date = current_date + timedelta(days=day)
    formatted_date = target_date.strftime('%Y년 %m월 %d일')

    ax.set_yticks(range(hall_count))
    ax.set_yticklabels(hall_names, fontsize=10)
    ax.set_title(f'{formatted_date} {cinema}점 상영 일정')
    fig.canvas.manager.set_window_title(f'{formatted_date} {cinema}점 상영 일정')

    ax.xaxis.set_major_locator(HourLocator())
    ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))

    plt.show()

def main():
    print("지역을 선택하세요:")
    for number, region_name in CL.regions['kr'].items():
        print(f"{number}. {region_name}", end='  ')

    region_number = int(input("\n지역번호: "))
    selected_region_kr = CL.regions['kr'][region_number]
    selected_region_en = CL.regions['en'][region_number]

    cinema_list = CL.cinemas[selected_region_en]
    print('-----------------------------------')
    print(f"{selected_region_kr}의 영화관 목록:")
    for idx, (cinema_name, _) in enumerate(cinema_list.items(), start=1):
        print(f"{idx}. {cinema_name}", end='   ')

    cinema_number = int(input("\n영화관 번호: "))
    selected_cinema = list(cinema_list.keys())[cinema_number - 1]
    cinemaID = cinema_list[selected_cinema]

    print('-----------------------------------')
    current_date = datetime.now()
    print(f'오늘 날짜 : {current_date.strftime('%Y년 %m월 %d일')}')
    dayafter = int(input("며칠 뒤에 볼건지 : "))

    movies = extract(cinemaID, dayafter)
    visualize_movie_schedule(movies, selected_cinema, dayafter)

if __name__ == '__main__':
    main()