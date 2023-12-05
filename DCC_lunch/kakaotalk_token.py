def get_access_token():

    def get_code(auth_url):

        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.common.by import By
        from selenium import webdriver
        import time, os

        options = webdriver.ChromeOptions()
        options.add_argument('headless')

        driver = webdriver.Chrome(ChromeDriverManager().install(), chrome_options = options)
        driver.get(auth_url)

        def send_txt(name, txt, isEnd = False):
            box = driver.find_element(By.NAME, name)
            box.send_keys(txt)
            if isEnd:
                box.submit()

        time.sleep(1)
        with open('DCC_lunch/secret.txt', 'r') as file:
            id, pw = file.read().split('\n')

        send_txt('loginKey', id)
        send_txt('password', pw, True)

        def parse_code(url):
            code = url[url.find('code=') + len('code=') : ]
            return code

        time.sleep(3)
        code = parse_code(driver.current_url)
        driver.quit()

        os.system('cls')

        return code

    def get_tokens(data):
        
        import requests

        response = requests.post(url, data = data)
        tokens = response.json()
        return tokens

    url = 'https://kauth.kakao.com/oauth/token'
    rest_id = 'd55f07da8340f396da22535de3cad5d9'
    redirect_url = 'https://localhost:5000'
    auth_url = f'https://kauth.kakao.com/oauth/authorize?client_id={rest_id}&redirect_uri={redirect_url}&response_type=code'
    code = get_code(auth_url)

    data = {
        'grant_type' : 'authorization_code',
        'client_id' : rest_id,
        'redirect_uri' : redirect_url,
        'code' : code,
        }

    tokens = get_tokens(data)
    return tokens['access_token']