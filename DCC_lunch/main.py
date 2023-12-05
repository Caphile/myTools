from kakaotalk_token import get_access_token as tk
from get_post import get_post_data as pd
import requests
import json

def send():
    header = {'Authorization' : f'Bearer {tk()}'}
    url = 'https://kapi.kakao.com/v2/api/talk/memo/default/send'
    data = {'template_object' : json.dumps(pd())}
    return requests.post(url, headers = header, data = data)

print(send().text)