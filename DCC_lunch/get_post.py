def get_post_data():
    from get_data import get_data as dt

    post = {
            'object_type' : 'text',
            'text' : '테스트용 메시지',
            'link' : {
                'web_url' : 'https://developers.kakao.com',
                'mobile_web_url' : 'https://developers.kakao.com'
            },
            'button_title' : '바로 확인'
        }
    return post