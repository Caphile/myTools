# -*- coding: utf-8 -*-
import os
import re
import time
import csv
import sys
import random
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------- 설정 영역 ----------
BASE = "https://hotels.naver.com"

# 지역 목록 (이름, 코드)
REGIONS: List[Tuple[str, str]] = [
    ("서울", "KR1000073"),
    ("인천", "KR1000532"),
    ("경기", "KR1000278"),
    ("강원", "KR1000013"),
    ("충북", "KR1000003"),
    ("충남", "KR1000008"),
    ("전북", "KR1000019"),
    ("전남", "KR1000015"),
    ("경북", "KR1000249"),
    ("경남", "KR1000243"),
    ("대구", "KR1000529"),
    ("광주", "KR1000531"),
    ("대전", "KR1000530"),
    ("울산", "KR1000534"),
    ("세종", "KR1001577"),
    ("제주", "KR1000533"),
]

# 숙소 유형 코드
PROPERTY_TYPES: Dict[int, str] = {
    0: "호텔",
    1: "모텔",
    8: "게스트하우스",
    12: "아파트",
    5: "호스텔",
    19: "레지던스 호텔",
    13: "홀리데이 하우스",
    2: "민박(Inn)",
    16: "빌라",
    23: "홈스테이",
    3: "민박(B&B)",
    17: "콘도",
    9: "캡슐 호텔",
    7: "펜션",
    6: "리조트",
}

# 기본 대기/말미(초)
DEFAULT_PAGE_PAUSE = 1.0   # 페이지 전환 후 말미
DEFAULT_DETAIL_PAUSE = 0.9 # 카드 클릭 후 말미

# ------------ 데이터 모델 ------------
@dataclass
class HotelRow:
    city: str                    # 지역명 (예: 서울)
    property_type: str           # 숙소유형 한글명 (예: 호텔)
    idx: int                     # 전체 인덱스
    region_idx: int              # 지역 내 인덱스
    name: str                    # 한글 이름
    name_en: str                 # 영문 이름
    grade: str                   # 성급/급
    tel: str                     # 전화번호
    address: str                 # 주소 (꼬리 텍스트 제거됨)
    detail_url: str              # 상세 페이지 URL
    website: str                 # 공식 웹사이트 URL

# ------------ 크롬 드라이버 ------------
def make_driver(
    headless: bool = True,
    clean_profile: bool = True,
    suppress_logs: bool = True,
    block_images: bool = True,
    disable_cache: bool = True,
    block_cookies: bool = False,
    user_agent: Optional[str] = None,
    window_size: str = "1280,900",
):
    """
    경량/조용/빠른 크롤링용 Chrome 드라이버 생성기.
    """
    opts = Options()

    # 새 헤드리스(권장)
    if headless:
        opts.add_argument("--headless=new")

    # 창 크기/안정성
    if window_size:
        opts.add_argument(f"--window-size={window_size}")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    # 프로필/쿠키/캐시 최소화
    if clean_profile:
        opts.add_argument("--incognito")
        opts.add_argument("--disable-application-cache")

    # 이미지/쿠키/캐시 관련 prefs
    prefs = {}
    if block_images:
        prefs["profile.managed_default_content_settings.images"] = 2  # 2=block
    if block_cookies:
        prefs["profile.default_content_setting_values.cookies"] = 2
        prefs["profile.block_third_party_cookies"] = True

    prefs["disk-cache-size"] = 0
    prefs["media-cache-size"] = 0
    if prefs:
        opts.add_experimental_option("prefs", prefs)

    # 브라우저 콘솔 로그 억제
    if suppress_logs:
        opts.add_argument("--log-level=3")
        opts.add_argument("--disable-logging")
        opts.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
        opts.add_argument("--disable-notifications")
        opts.add_argument("--allow-running-insecure-content")

    if user_agent:
        opts.add_argument(f"--user-agent={user_agent}")

    # 드라이버 서비스 로그도 버리기
    service = ChromeService(log_path=os.devnull) if suppress_logs else ChromeService()

    driver = webdriver.Chrome(service=service, options=opts)

    # DevTools로 네트워크 캐시 완전 비활성화
    if disable_cache:
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
        except Exception:
            pass

    driver.set_page_load_timeout(45)
    driver.implicitly_wait(0)
    return driver

# ------------ 도우미 ------------
def list_url(region_code: str, property_type: int, adult: int = 2, page: int = 1) -> str:
    # propertyTypes 파라미터로 유형 지정
    return f"{BASE}/{region_code}/hotels?adultCnt={adult}&pageIndex={page}&propertyTypes={property_type}"

def sleep_jitter(base: float):
    time.sleep(base + random.uniform(0.05, 0.25))

def clean_address(raw: str) -> str:
    """주소에서 ‘위치/길찾기/거리뷰’ 꼬리 제거."""
    if not raw:
        return ""
    s = re.sub(r"\s+", " ", raw).strip()

    # '위치 길찾기 거리뷰' 한 덩어리 제거 (중간에 공백/nbsp 대응)
    s = re.sub(r"(위치\s*길찾기\s*거리뷰)\s*$", "", s)

    # 혹시 단독 키워드가 중간/끝에 섞여 있으면 제거
    tail_words = ["위치", "길찾기", "거리뷰"]
    for w in tail_words:
        s = re.sub(rf"\s*{w}\s*$", "", s)
        s = re.sub(rf"\s*{w}\s*", " ", s)

    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

def text_or_empty(el) -> str:
    try:
        return el.text.strip()
    except Exception:
        return ""

def safe_find(driver, by, value, multi=False, timeout=8):
    try:
        if multi:
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_all_elements_located((by, value))
            )
        else:
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
    except Exception:
        return [] if multi else None

# ------------ 파서 ------------
def parse_detail_panel(driver) -> Dict[str, str]:
    """
    상세 패널(같은 창 내 Info_* 섹션)에서 정보 파싱.
    """
    out = {
        "name": "",
        "name_en": "",
        "grade": "",
        "tel": "",
        "address": "",
        "website": "",
        "detail_url": driver.current_url
    }

    root = safe_find(driver, By.CSS_SELECTOR, "div.Info_Info__Nutkw", timeout=12)
    if not root:
        return out

    # 한글명 / 영문명 / 성급
    name_el = safe_find(driver, By.CSS_SELECTOR, "h3.Info_name__ogaJE span.Info_txt__5XJl0", timeout=5)
    if name_el:
        out["name"] = text_or_empty(name_el)

    en_el = safe_find(driver, By.CSS_SELECTOR, "i.Info_eng__InlcK", timeout=2)
    if en_el:
        out["name_en"] = text_or_empty(en_el)

    grade_el = safe_find(driver, By.CSS_SELECTOR, "div.Info_grade__Xn_uy i.Info_gradetxt___V9AF", timeout=2)
    if grade_el:
        out["grade"] = text_or_empty(grade_el)

    # 홈페이지
    homepage_el = safe_find(driver, By.CSS_SELECTOR, "li.Info_item__bDb4b.homepage a.Info_link__ikjyU", timeout=2)
    if homepage_el:
        try:
            out["website"] = homepage_el.get_attribute("href") or ""
        except Exception:
            pass

    # 주소
    addr_li = safe_find(driver, By.CSS_SELECTOR, "li.Info_item__bDb4b.address span.Info_txt__5XJl0", timeout=3)
    if addr_li:
        out["address"] = clean_address(text_or_empty(addr_li))

    # 전화
    tel_li = safe_find(driver, By.CSS_SELECTOR, "li.Info_item__bDb4b [data-label='tel'] + div span.Info_txt__5XJl0", timeout=2)
    if not tel_li:
        tel_li = safe_find(driver, By.CSS_SELECTOR, "li.Info_item__bDb4b i[data-label='tel'] ~ div span.Info_txt__5XJl0", timeout=2)
    if tel_li:
        tel_text = text_or_empty(tel_li)
        tel_text = tel_text.replace("복사", "").strip()
        out["tel"] = tel_text

    try:
        out["detail_url"] = driver.current_url
    except Exception:
        pass

    return out

def collect_cards(driver) -> List:
    """리스트 페이지에서 호텔 카드 요소 목록 수집."""
    # ‘예약 가능한 호텔이 없습니다’ → 빈 리스트
    no_item = driver.find_elements(By.CSS_SELECTOR, "div.Condition_NoItemWithCondition__hPSou")
    if no_item:
        return []

    # 일반 카드
    cards = driver.find_elements(By.CSS_SELECTOR, "ul.SearchList_SearchList___ce0v li.SearchList_item__SrHOi div.SearchList_HotelItem__RRmaZ")
    if cards:
        return cards

    return []

def open_card(driver, card, detail_pause: float):
    """카드 클릭 → 상세 패널 열기"""
    try:
        info = card.find_element(By.CSS_SELECTOR, "div.SearchList_InfoArea__qp7VR")
    except Exception:
        info = card

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", info)
    sleep_jitter(0.15)
    info.click()
    sleep_jitter(detail_pause)

    WebDriverWait(driver, 12).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.Info_Info__Nutkw"))
    )

def go_list_page(driver, region_code: str, ptype: int, page: int,
                 page_pause: float) -> bool:
    """리스트 페이지 진입."""
    url = list_url(region_code, ptype, page=page)
    driver.get(url)
    print(f"[PAGE {page}] {url}")
    sleep_jitter(page_pause)

    try:
        WebDriverWait(driver, 10).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ul.SearchList_SearchList___ce0v")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.Condition_NoItemWithCondition__hPSou"))
            )
        )
    except Exception:
        sleep_jitter(0.6)

    return True

# ------------ 체크포인트 저장 ------------
def write_csv(path: str, rows: List[HotelRow], header: bool = False):

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if header:
            w.writerow([
                "idx","city","region_idx",
                "name","name_en","property_type",
                "grade","tel","address",
                "rating_hotelscombined","rating_booking","rating_tripadvisor","rating_naver",
                "website","detail_url",
            ])

        for r in rows:
            w.writerow([
                r.idx, r.city, r.region_idx,
                r.name, r.name_en, r.property_type,
                r.grade, r.tel, r.address,
                getattr(r, "rating_hotelscombined", ""),
                getattr(r, "rating_booking", ""),
                getattr(r, "rating_tripadvisor", ""),
                getattr(r, "rating_naver", ""),
                r.website, r.detail_url,
            ])

def write_failures(path: str, failures: List[Dict], header: bool = False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if header:
            w.writerow(["city", "property_type", "page", "card_index", "reason", "page_url"])
        for it in failures:
            w.writerow([it.get("city",""), it.get("property_type",""), it.get("page",0),
                        it.get("card_index",-1), it.get("reason",""), it.get("page_url","")])

# ------------ 평점 파싱(옵션) ------------
def parse_ratings_from_detail(driver) -> Dict[str, str]:
    """상세 패널의 외부 사이트 평점 파싱."""
    out = {"hotelscombined": "", "booking": "", "tripadvisor": "", "naver": ""}
    pairs = [
        ("호텔스컴바인", "hotelscombined"),
        ("부킹닷컴", "booking"),
        ("트립어드바이저", "tripadvisor"),
        ("네이버", "naver"),
    ]
    try:
        blocks = driver.find_elements(By.CSS_SELECTOR, "li.Info_item__bDb4b i[data-label='rating'] ~ div span.Info_txt__5XJl0")
        if not blocks:
            blocks = driver.find_elements(By.CSS_SELECTOR, "li.Info_item__bDb4b")
        for b in blocks:
            try:
                a = b.find_element(By.CSS_SELECTOR, "a.Info_link__ikjyU")
                label = a.text.strip()
                val_el = b.find_element(By.CSS_SELECTOR, "b.Info_current__Ocnim")
                val = val_el.text.strip()
                for kor, key in pairs:
                    if kor in label:
                        out[key] = val
                        break
            except Exception:
                continue
    except Exception:
        pass
    return out

# ------------ 메인 크롤링 루프 ------------
def crawl_region_property(driver,
                          city: str,
                          region_code: str,
                          property_type_code: int,
                          page_pause: float = DEFAULT_PAGE_PAUSE,
                          detail_pause: float = DEFAULT_DETAIL_PAUSE,
                          checkpoint_enabled: bool = True,
                          checkpoint_every: int = 20,
                          out_csv: str = "out/results.csv",
                          fail_csv: str = "out/failures.csv",
                          start_page: int = 1,
                          max_pages: Optional[int] = None,
                          global_index_start: int = 1,
                          region_index_start: int = 1):
    """
    한 지역 + 숙소유형 전체 페이지 크롤링.
    반환: (수집성공개수, 실패개수, global_idx_last, region_idx_last)
    """
    results_buffer: List[HotelRow] = []
    failures_buffer: List[Dict] = []
    total_ok, total_fail = 0, 0
    global_idx = global_index_start
    region_idx = region_index_start

    # 체크포인트 헤더(최초 1회)
    if checkpoint_enabled:
        if not os.path.exists(out_csv):
            write_csv(out_csv, [], header=True)
        if not os.path.exists(fail_csv):
            write_failures(fail_csv, [], header=True)

    ptype_name = PROPERTY_TYPES.get(property_type_code, f"type_{property_type_code}")

    page = start_page
    while True:
        if max_pages and page > max_pages:
            print(f"[STOP] page>{max_pages} → break")
            break

        ok = go_list_page(driver, region_code, property_type_code, page, page_pause=page_pause)
        if not ok:
            print(f"[WARN] 페이지 로드 실패: p={page}")
            break

        cards = collect_cards(driver)
        print(f"[PAGE {page}] cards: {len(cards)}")

        # 마지막 페이지(예약 가능 호텔 없음) or 카드가 0개 → 종료
        if len(cards) == 0:
            print("[STOP] 카드 없음(또는 조건 불가) → 종료")
            break

        for ci, card in enumerate(cards, start=1):
            try:
                open_card(driver, card, detail_pause=detail_pause)
            except Exception as e:
                failures_buffer.append({
                    "city": city, "property_type": ptype_name, "page": page,
                    "card_index": ci, "reason": f"open_card:{repr(e)}",
                    "page_url": driver.current_url
                })
                total_fail += 1
                if checkpoint_enabled and len(failures_buffer) >= max(1, checkpoint_every//2):
                    write_failures(fail_csv, failures_buffer, header=False)
                    failures_buffer.clear()
                continue

            # 상세 파싱
            detail = parse_detail_panel(driver)
            ratings = parse_ratings_from_detail(driver)
            if not any(detail.values()):
                failures_buffer.append({
                    "city": city, "property_type": ptype_name, "page": page,
                    "card_index": ci, "reason": "parse_detail:empty",
                    "page_url": driver.current_url
                })
                total_fail += 1
                if checkpoint_enabled and len(failures_buffer) >= max(1, checkpoint_every//2):
                    write_failures(fail_csv, failures_buffer, header=False)
                    failures_buffer.clear()
                continue

            row = HotelRow(
                city=city,
                property_type=ptype_name,
                idx=global_idx,
                region_idx=region_idx,
                name=detail.get("name",""),
                name_en=detail.get("name_en",""),
                grade=detail.get("grade",""),
                tel=detail.get("tel",""),
                address=detail.get("address",""),
                detail_url=detail.get("detail_url",""),
                website=detail.get("website",""),
            )
            # 평점 필드(객체에 속성 동적 추가)
            setattr(row, "rating_hotelscombined", ratings.get("hotelscombined",""))
            setattr(row, "rating_booking", ratings.get("booking",""))
            setattr(row, "rating_tripadvisor", ratings.get("tripadvisor",""))
            setattr(row, "rating_naver", ratings.get("naver",""))

            # 콘솔 추적
            print(f"  → [{row.idx}] {row.city}/{row.property_type} | {row.name} | {row.grade} | {row.tel} | {row.address}")

            results_buffer.append(row)
            total_ok += 1
            global_idx += 1
            region_idx += 1

            # 체크포인트 저장
            if checkpoint_enabled and (len(results_buffer) >= checkpoint_every):
                write_csv(out_csv, results_buffer, header=False)
                results_buffer.clear()

        # 다음 페이지
        page += 1

    # 잔여 저장
    if results_buffer:
        if checkpoint_enabled:
            write_csv(out_csv, results_buffer, header=False)
        results_buffer.clear()

    if failures_buffer:
        if checkpoint_enabled:
            write_failures(fail_csv, failures_buffer, header=False)
        failures_buffer.clear()

    return total_ok, total_fail, global_idx - 1, region_idx - 1

# ------------ 전체 실행 ------------
def crawl_all(headless: bool = True,
              checkpoint_enabled: bool = True,
              checkpoint_every: int = 20,
              out_csv: str = "out/results.csv",
              fail_csv: str = "out/failures.csv",
              page_pause: float = DEFAULT_PAGE_PAUSE,
              detail_pause: float = DEFAULT_DETAIL_PAUSE,
              property_types: Optional[List[int]] = None,
              max_pages_per_combo: Optional[int] = None):
    """
    모든 지역 × 숙소유형 조합 크롤링.
    """
    if property_types is None:
        property_types = list(PROPERTY_TYPES.keys())

    driver = make_driver(headless=headless, clean_profile=True, suppress_logs=True)

    # 헤더 파일 준비
    if not os.path.exists(out_csv):
        write_csv(out_csv, [], header=True)
    if not os.path.exists(fail_csv):
        write_failures(fail_csv, [], header=True)

    global_idx = 1
    for city, region_code in REGIONS:
        region_idx = 1
        for ptype in property_types:
            print(f"\n===== {city} / {PROPERTY_TYPES.get(ptype, ptype)} 시작 =====")
            ok_cnt, fail_cnt, global_last, region_last = crawl_region_property(
                driver=driver,
                city=city,
                region_code=region_code,
                property_type_code=ptype,
                page_pause=page_pause,
                detail_pause=detail_pause,
                checkpoint_enabled=checkpoint_enabled,
                checkpoint_every=checkpoint_every,
                out_csv=out_csv,
                fail_csv=fail_csv,
                start_page=1,
                max_pages=max_pages_per_combo,
                global_index_start=global_idx,
                region_index_start=region_idx
            )
            print(f"[DONE] {city}/{PROPERTY_TYPES.get(ptype, ptype)} → ok:{ok_cnt}, fail:{fail_cnt}")
            global_idx = global_last + 1
            region_idx = 1  # 다음 유형부터 지역 내 인덱스는 다시 1부터

    driver.quit()
    print("\n=== 전체 완료 ===")
    print(f"결과: {out_csv}")
    print(f"실패: {fail_csv}")

# ------------ 엔트리 포인트 ------------
if __name__ == "__main__":
    crawl_all(
        headless=False,              # 창 없이 실행(True)
        checkpoint_enabled=True,     # 중간 저장 사용
        checkpoint_every=50,         # N개 단위로 결과 CSV append
        out_csv="out/results.csv",   # 결과 파일
        fail_csv="out/failures.csv", # 실패 목록 파일
        page_pause=1.0,              # 페이지 전환 말미
        detail_pause=0.9,            # 상세 열림 말미
        property_types=list(PROPERTY_TYPES.keys()),  # 모든 유형
        max_pages_per_combo=None     # None이면 끝까지(‘카드 없음’ 나오면 종료)
    )
