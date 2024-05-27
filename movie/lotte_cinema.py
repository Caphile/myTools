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

def extract(cinemaID=1007, day=0):
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

def visualize_movie_schedule(movies, day=0):
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
    ax.set_title(f'{formatted_date} 상영 일정')
    fig.canvas.manager.set_window_title('상영 일정')

    ax.xaxis.set_major_locator(HourLocator())
    ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))

    plt.show()

if __name__ == '__main__':
    dayafter = 2
    cinemaID = 1016
    movies = extract(day=dayafter)
    visualize_movie_schedule(movies, dayafter)