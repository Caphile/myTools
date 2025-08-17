# -*- coding: utf-8 -*-
"""
네이버 호텔 크롤러 (품질 우선 최적화 + 멀티프로세스 병렬 + 워커 프리픽스 로그)
- 단위 작업: (지역, 숙소유형) 조합
- 프로세스 별 독립 Chrome 프로필 사용(충돌 방지)
- 상세 패널 '텍스트 로딩 완료'까지 대기 + 카드 타이틀 백업으로 이름 누락 방지
- 조합별 CSV 저장 → 최종 병합(중복 제거 / region_idx & idx 재계산)
- 모든 콘솔 출력 앞에 [W{번호}] 프리픽스 부착
"""

import os
import re
import time
import csv
import sys
import random
import tempfile
import shutil
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)

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
DEFAULT_DETAIL_PAUSE = 1.0 # 카드 클릭 후 말미(품질 우선)

# ------------ 유틸 로그 ------------
def log(prefix: str, msg: str):
    print(f"{prefix} {msg}", flush=True)

# ------------ 데이터 모델 ------------
@dataclass
class HotelRow:
    city: str
    property_type: str
    idx: int
    region_idx: int
    name: str
    name_en: str
    grade: str
    tel: str
    address: str
    detail_url: str
    website: str

# ------------ 유틸 ------------
def list_url(region_code: str, property_type: int, adult: int = 2, page: int = 1) -> str:
    return f"{BASE}/{region_code}/hotels?adultCnt={adult}&pageIndex={page}&propertyTypes={property_type}"

def sleep_jitter(base: float):
    time.sleep(base + random.uniform(0.05, 0.25))

def clean_address(raw: str) -> str:
    if not raw:
        return ""
    s = re.sub(r"\s+", " ", raw).strip()
    s = re.sub(r"(위치\s*길찾기\s*거리뷰)\s*$", "", s)
    for w in ["위치", "길찾기", "거리뷰"]:
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

def wait_text_nonempty(driver, css: str, timeout: int = 8) -> str:
    def _ok(drv):
        el = drv.find_element(By.CSS_SELECTOR, css)
        txt = (el.text or "").strip()
        return txt if txt else False
    return WebDriverWait(driver, timeout).until(_ok)

def safe_find(ctx, by, value, multi=False, timeout=8):
    try:
        if multi:
            return WebDriverWait(ctx, timeout).until(EC.presence_of_all_elements_located((by, value)))
        else:
            return WebDriverWait(ctx, timeout).until(EC.presence_of_element_located((by, value)))
    except Exception:
        return [] if multi else None

# ------------ 드라이버 ------------
def make_driver(
    headless: bool = True,
    user_data_dir: Optional[str] = None,
    suppress_logs: bool = True,
    block_images: bool = True,
    disable_cache: bool = True,
    block_cookies: bool = False,
    user_agent: Optional[str] = None,
    window_size: str = "1280,900",
):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--no-first-run")
        opts.add_argument("--no-default-browser-check")
        opts.add_argument("--disable-extensions")

    if window_size:
        opts.add_argument(f"--window-size={window_size}")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    if user_data_dir:
        opts.add_argument(f"--user-data-dir={user_data_dir}")
    else:
        opts.add_argument("--incognito")
        opts.add_argument("--disable-application-cache")

    prefs = {}
    if block_images:
        prefs["profile.managed_default_content_settings.images"] = 2
    if block_cookies:
        prefs["profile.default_content_setting_values.cookies"] = 2
        prefs["profile.block_third_party_cookies"] = True
    prefs["disk-cache-size"] = 0
    prefs["media-cache-size"] = 0
    if prefs:
        opts.add_experimental_option("prefs", prefs)

    if suppress_logs:
        opts.add_argument("--log-level=3")
        opts.add_argument("--disable-logging")
        opts.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
        opts.add_argument("--disable-notifications")
        opts.add_argument("--allow-running-insecure-content")

    if user_agent:
        opts.add_argument(f"--user-agent={user_agent}")

    service = ChromeService(log_path=os.devnull) if suppress_logs else ChromeService()
    driver = webdriver.Chrome(service=service, options=opts)

    if disable_cache:
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
        except Exception:
            pass

    driver.set_page_load_timeout(45)
    driver.implicitly_wait(0)
    return driver

# ------------ 파서/수집 ------------
def card_name_fallback(card) -> str:
    sels = [
        "div[class*=SearchList_InfoArea] h3",
        "h3", "strong"
    ]
    for sel in sels:
        try:
            els = card.find_elements(By.CSS_SELECTOR, sel)
        except StaleElementReferenceException:
            return ""
        if els:
            t = (els[0].text or "").strip()
            if t:
                return t
    return ""

def parse_detail_panel(driver, fallback_name: str = "") -> Dict[str, str]:
    out = {"name":"", "name_en":"", "grade":"", "tel":"", "address":"", "website":"", "detail_url":driver.current_url}
    root = safe_find(driver, By.CSS_SELECTOR, "div.Info_Info__Nutkw", timeout=10)
    if not root:
        out["name"] = fallback_name
        return out

    name_el = safe_find(driver, By.CSS_SELECTOR, "h3.Info_name__ogaJE span.Info_txt__5XJl0", timeout=3)
    if name_el:
        out["name"] = text_or_empty(name_el)
    if not out["name"]:
        try:
            out["name"] = wait_text_nonempty(driver, "h3.Info_name__ogaJE span.Info_txt__5XJl0", timeout=6)
        except Exception:
            pass
    if not out["name"] and fallback_name:
        out["name"] = fallback_name

    en_el = safe_find(driver, By.CSS_SELECTOR, "i.Info_eng__InlcK", timeout=2)
    if en_el:
        out["name_en"] = text_or_empty(en_el)

    grade_el = safe_find(driver, By.CSS_SELECTOR, "div.Info_grade__Xn_uy i.Info_gradetxt___V9AF", timeout=2)
    if grade_el:
        out["grade"] = text_or_empty(grade_el)

    homepage_el = safe_find(driver, By.CSS_SELECTOR, "li.Info_item__bDb4b.homepage a.Info_link__ikjyU", timeout=2)
    if homepage_el:
        try:
            out["website"] = homepage_el.get_attribute("href") or ""
        except Exception:
            pass

    addr_li = safe_find(driver, By.CSS_SELECTOR, "li.Info_item__bDb4b.address span.Info_txt__5XJl0", timeout=3)
    if addr_li:
        out["address"] = clean_address(text_or_empty(addr_li))

    tel_li = safe_find(driver, By.CSS_SELECTOR, "li.Info_item__bDb4b [data-label='tel'] + div span.Info_txt__5XJl0", timeout=2)
    if not tel_li:
        tel_li = safe_find(driver, By.CSS_SELECTOR, "li.Info_item__bDb4b i[data-label='tel'] ~ div span.Info_txt__5XJl0", timeout=2)
    if tel_li:
        tel_text = text_or_empty(tel_li).replace("복사", "").strip()
        out["tel"] = tel_text

    try:
        out["detail_url"] = driver.current_url
    except Exception:
        pass

    return out

def parse_ratings_from_detail(driver) -> Dict[str, str]:
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

def collect_cards(driver) -> List:
    no_item = driver.find_elements(By.CSS_SELECTOR, "div.Condition_NoItemWithCondition__hPSou")
    if no_item:
        return []
    cards = driver.find_elements(By.CSS_SELECTOR, "ul[class*=SearchList_SearchList] li[class*=SearchList_item] div[class*=HotelItem]")
    if cards:
        return cards
    return []

def open_card(driver, card, detail_pause: float, prefix: str):
    try:
        info = card.find_element(By.CSS_SELECTOR, "div[class*=SearchList_InfoArea]")
    except Exception:
        info = card
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", info)
    sleep_jitter(0.12)
    try:
        info.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", info)

    WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.Info_Info__Nutkw")))
    try:
        _ = wait_text_nonempty(driver, "h3.Info_name__ogaJE span.Info_txt__5XJl0", timeout=8)
    except Exception:
        pass
    sleep_jitter(detail_pause)

def go_list_page(driver, region_code: str, ptype: int, page: int,
                 page_pause: float, prefix: str) -> bool:
    url = list_url(region_code, ptype, page=page)
    driver.get(url)
    log(prefix, f"[PAGE {page}] {url}")
    sleep_jitter(page_pause)
    try:
        WebDriverWait(driver, 10).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ul[class*=SearchList_SearchList]")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.Condition_NoItemWithCondition__hPSou")),
            )
        )
    except Exception:
        sleep_jitter(0.6)
    return True

def has_next(driver) -> bool:
    try:
        btns = driver.find_elements(By.CSS_SELECTOR, "a[class*='Pagination_next'], button[aria-label='다음']")
        if not btns:
            return True
        return any(b.is_enabled() and b.is_displayed() for b in btns)
    except Exception:
        return True

# ------------ 파일 I/O ------------
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

# ------------ 단일 조합 수집 루프 ------------
def crawl_region_property(driver,
                          city: str,
                          region_code: str,
                          property_type_code: int,
                          page_pause: float = DEFAULT_PAGE_PAUSE,
                          detail_pause: float = DEFAULT_DETAIL_PAUSE,
                          checkpoint_enabled: bool = True,
                          checkpoint_every: int = 50,
                          out_csv: str = "out/results.csv",
                          fail_csv: str = "out/failures.csv",
                          start_page: int = 1,
                          max_pages: Optional[int] = None,
                          global_index_start: int = 1,
                          region_index_start: int = 1,
                          prefix: str = "[W?]"):
    """
    한 지역 + 숙소유형 전체 페이지 크롤링.
    반환: (수집성공개수, 실패개수, global_idx_last, region_idx_last)
    """
    results_buffer: List[HotelRow] = []
    failures_buffer: List[Dict] = []
    total_ok, total_fail = 0, 0
    global_idx = global_index_start
    region_idx = region_index_start

    if checkpoint_enabled:
        if not os.path.exists(out_csv):
            write_csv(out_csv, [], header=True)
        if not os.path.exists(fail_csv):
            write_failures(fail_csv, [], header=True)

    ptype_name = PROPERTY_TYPES.get(property_type_code, f"type_{property_type_code}")
    seen = set()

    page = start_page
    empty_runs = 0

    while True:
        if max_pages and page > max_pages:
            log(prefix, f"[STOP] page>{max_pages} → break")
            break

        ok = go_list_page(driver, region_code, property_type_code, page, page_pause=page_pause, prefix=prefix)
        if not ok:
            log(prefix, f"[WARN] 페이지 로드 실패: p={page}")
            break

        cards = collect_cards(driver)
        log(prefix, f"[PAGE {page}] cards: {len(cards)}")

        if len(cards) == 0:
            empty_runs += 1
            if empty_runs >= 2 or not has_next(driver):
                log(prefix, "[STOP] 카드 없음 or 다음 없음 → 종료")
                break
            page += 1
            continue
        else:
            empty_runs = 0

        for ci, card in enumerate(cards, start=1):
            try:
                fb_name = card_name_fallback(card)
                open_card(driver, card, detail_pause=detail_pause, prefix=prefix)
            except (TimeoutException, StaleElementReferenceException, ElementClickInterceptedException) as e:
                failures_buffer.append({
                    "city": city, "property_type": ptype_name, "page": page,
                    "card_index": ci, "reason": type(e).__name__,
                    "page_url": driver.current_url
                })
                total_fail += 1
                if checkpoint_enabled and len(failures_buffer) >= max(1, checkpoint_every//2):
                    write_failures(fail_csv, failures_buffer, header=False)
                    failures_buffer.clear()
                continue

            detail = parse_detail_panel(driver, fallback_name=fb_name)
            ratings = parse_ratings_from_detail(driver)

            durl = detail.get("detail_url","")
            if durl and durl in seen:
                continue
            if durl:
                seen.add(durl)

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
            setattr(row, "rating_hotelscombined", ratings.get("hotelscombined",""))
            setattr(row, "rating_booking", ratings.get("booking",""))
            setattr(row, "rating_tripadvisor", ratings.get("tripadvisor",""))
            setattr(row, "rating_naver", ratings.get("naver",""))

            log(prefix, f"→ [{row.idx}] {row.city}/{row.property_type} | {row.name} | {row.grade} | {row.tel} | {row.address}")

            results_buffer.append(row)
            total_ok += 1
            global_idx += 1
            region_idx += 1

            if checkpoint_enabled and (len(results_buffer) >= checkpoint_every):
                write_csv(out_csv, results_buffer, header=False)
                results_buffer.clear()

        page += 1

    if results_buffer and checkpoint_enabled:
        write_csv(out_csv, results_buffer, header=False)
        results_buffer.clear()

    if failures_buffer and checkpoint_enabled:
        write_failures(fail_csv, failures_buffer, header=False)
        failures_buffer.clear()

    return total_ok, total_fail, global_idx - 1, region_idx - 1

# ------------ 멀티프로세스 워커 & 병합 ------------
def out_paths(base_dir: str, city: str, ptype_name: str):
    os.makedirs(base_dir, exist_ok=True)
    tag = f"{city}_{ptype_name}"
    return (os.path.join(base_dir, f"{tag}.csv"),
            os.path.join(base_dir, f"{tag}_fail.csv"))

def run_combo(task):
    """
    task = (city, region_code, ptype_code, args, wid)
    각 프로세스가 독립 Chrome을 띄워 (city, ptype) 하나 처리
    """
    city, region_code, ptype, args, wid = task
    prefix = f"[W{wid}]"
    ptype_name = PROPERTY_TYPES.get(ptype, f"type_{ptype}")

    tmp_profile = tempfile.mkdtemp(prefix=f"selenium_{city}_{ptype}_")
    driver = None
    try:
        log(prefix, f"시작 → {city}/{ptype_name}")
        driver = make_driver(
            headless=args.get("headless", True),
            user_data_dir=tmp_profile,          # 프로세스별 프로필(충돌 방지)
            suppress_logs=True,
            block_images=True,
            disable_cache=True,
        )

        out_csv, fail_csv = out_paths(args["tmp_out_dir"], city, ptype_name)
        if not os.path.exists(out_csv):
            write_csv(out_csv, [], header=True)
        if not os.path.exists(fail_csv):
            write_failures(fail_csv, [], header=True)

        ok_cnt, fail_cnt, g_last, r_last = crawl_region_property(
            driver=driver,
            city=city,
            region_code=region_code,
            property_type_code=ptype,
            page_pause=args.get("page_pause", DEFAULT_PAGE_PAUSE),
            detail_pause=args.get("detail_pause", DEFAULT_DETAIL_PAUSE),
            checkpoint_enabled=True,
            checkpoint_every=args.get("checkpoint_every", 50),
            out_csv=out_csv,
            fail_csv=fail_csv,
            start_page=1,
            max_pages=args.get("max_pages_per_combo", None),
            global_index_start=1,
            region_index_start=1,
            prefix=prefix
        )
        log(prefix, f"완료 → {city}/{ptype_name} ok:{ok_cnt} fail:{fail_cnt}")
        return {"city": city, "ptype": ptype_name, "ok": ok_cnt, "fail": fail_cnt, "out_csv": out_csv}
    finally:
        try:
            if driver: driver.quit()
        except Exception: pass
        shutil.rmtree(tmp_profile, ignore_errors=True)

def merge_and_polish(tmp_dir: str, final_csv: str, final_fail_csv: str, prefix: str):
    files = [os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir)
             if f.endswith(".csv") and not f.endswith("_fail.csv")]
    fail_files = [os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir)
                  if f.endswith("_fail.csv")]

    if files:
        dfs = []
        for f in files:
            try:
                df = pd.read_csv(f, dtype=str)
                dfs.append(df)
            except Exception as e:
                log(prefix, f"[SKIP] {f} 읽기 실패: {e}")

        if dfs:
            all_df = pd.concat(dfs, ignore_index=True)
            if "detail_url" in all_df.columns:
                all_df["__dupk"] = all_df["detail_url"].fillna("") + "|" + all_df["name"].fillna("") + "|" + all_df["address"].fillna("")
            else:
                all_df["__dupk"] = all_df["name"].fillna("") + "|" + all_df["address"].fillna("")
            all_df = all_df.drop_duplicates("__dupk").drop(columns="__dupk")

            all_df = all_df.sort_values(["city", "property_type", "name"], na_position="last")
            all_df["region_idx"] = (all_df.groupby(["city", "property_type"]).cumcount() + 1).astype(int)
            all_df["idx"] = range(1, len(all_df) + 1)

            cols = ["idx","city","region_idx","name","name_en","property_type",
                    "grade","tel","address","rating_hotelscombined","rating_booking",
                    "rating_tripadvisor","rating_naver","website","detail_url"]
            for c in cols:
                if c not in all_df.columns:
                    all_df[c] = ""
            all_df = all_df[cols]

            os.makedirs(os.path.dirname(final_csv), exist_ok=True)
            all_df.to_csv(final_csv, index=False, encoding="utf-8-sig")
            log(prefix, f"[MERGE] {len(all_df)} rows → {final_csv}")
        else:
            log(prefix, "[WARN] 병합할 결과 DF 없음")
    else:
        log(prefix, "[WARN] 결과 파일 없음")

    if fail_files:
        fdfs = []
        for f in fail_files:
            try:
                df = pd.read_csv(f, dtype=str)
                fdfs.append(df)
            except Exception as e:
                log(prefix, f"[SKIP] {f} 읽기 실패: {e}")
        if fdfs:
            all_fail = pd.concat(fdfs, ignore_index=True)
            os.makedirs(os.path.dirname(final_fail_csv), exist_ok=True)
            all_fail.to_csv(final_fail_csv, index=False, encoding="utf-8-sig")
            log(prefix, f"[MERGE FAIL] {len(all_fail)} rows → {final_fail_csv}")

# ------------ 멀티프로세스 오케스트레이터 ------------
def crawl_all_mp(max_workers: int = 6,
                 headless: bool = True,
                 checkpoint_every: int = 50,
                 tmp_out_dir: str = "out/tmp",
                 final_out_csv: str = "out/results.csv",
                 final_fail_csv: str = "out/failures.csv",
                 page_pause: float = DEFAULT_PAGE_PAUSE,
                 detail_pause: float = DEFAULT_DETAIL_PAUSE,
                 property_types: Optional[List[int]] = None,
                 max_pages_per_combo: Optional[int] = None):

    if property_types is None:
        property_types = list(PROPERTY_TYPES.keys())

    os.makedirs(tmp_out_dir, exist_ok=True)

    args = {
        "headless": headless,
        "checkpoint_every": checkpoint_every,
        "tmp_out_dir": tmp_out_dir,
        "page_pause": page_pause,
        "detail_pause": detail_pause,
        "max_pages_per_combo": max_pages_per_combo,
    }

    tasks = []
    wid = 1
    for city, region_code in REGIONS:
        for ptype in property_types:
            tasks.append((city, region_code, ptype, args, wid))
            wid += 1

    master_prefix = "[MASTER]"
    log(master_prefix, f"[PLAN] 총 작업 수: {len(tasks)}, workers={max_workers}")
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(run_combo, t) for t in tasks]
        for fut in as_completed(futs):
            try:
                r = fut.result()
                results.append(r)
                log(master_prefix, f"[DONE] {r['city']}/{r['ptype']} ok:{r['ok']} fail:{r['fail']}")
            except Exception as e:
                log(master_prefix, f"[ERROR] 작업 실패: {e}")

    merge_and_polish(tmp_out_dir, final_out_csv, final_fail_csv, prefix=master_prefix)
    log(master_prefix, "=== 전체 완료 ===")
    log(master_prefix, f"결과: {final_out_csv}")
    log(master_prefix, f"실패: {final_fail_csv}")

# ------------ 단일 프로세스(디버그용) ------------
def crawl_all_single(headless: bool = True,
                     checkpoint_every: int = 50,
                     out_csv: str = "out/results.csv",
                     fail_csv: str = "out/failures.csv",
                     page_pause: float = DEFAULT_PAGE_PAUSE,
                     detail_pause: float = DEFAULT_DETAIL_PAUSE,
                     property_types: Optional[List[int]] = None,
                     max_pages_per_combo: Optional[int] = None):
    if property_types is None:
        property_types = list(PROPERTY_TYPES.keys())

    driver = make_driver(headless=headless, user_data_dir=None, suppress_logs=True)

    if not os.path.exists(out_csv):
        write_csv(out_csv, [], header=True)
    if not os.path.exists(fail_csv):
        write_failures(fail_csv, [], header=True)

    global_idx = 1
    prefix = "[W1]"
    for city, region_code in REGIONS:
        region_idx = 1
        for ptype in property_types:
            log(prefix, f"===== {city} / {PROPERTY_TYPES.get(ptype, ptype)} 시작 =====")
            ok_cnt, fail_cnt, global_last, region_last = crawl_region_property(
                driver=driver,
                city=city,
                region_code=region_code,
                property_type_code=ptype,
                page_pause=page_pause,
                detail_pause=detail_pause,
                checkpoint_enabled=True,
                checkpoint_every=checkpoint_every,
                out_csv=out_csv,
                fail_csv=fail_csv,
                start_page=1,
                max_pages=max_pages_per_combo,
                global_index_start=global_idx,
                region_index_start=region_idx,
                prefix=prefix
            )
            log(prefix, f"[DONE] {city}/{PROPERTY_TYPES.get(ptype, ptype)} → ok:{ok_cnt}, fail:{fail_cnt}")
            global_idx = global_last + 1
            region_idx = 1

    try:
        driver.quit()
    except Exception:
        pass
    log(prefix, "=== 단일 프로세스 완료 ===")
    log(prefix, f"결과: {out_csv}")
    log(prefix, f"실패: {fail_csv}")

# ------------ 엔트리 포인트 ------------
if __name__ == "__main__":
    import multiprocessing as mp
    mp.freeze_support()

    workers = int(input("프로세서 수 : "))

    # 병렬 실행
    crawl_all_mp(
        max_workers=workers,           # 리소스에 맞게 조절
        headless=False,                # 디버그 시 False
        checkpoint_every=50,
        tmp_out_dir="out/tmp",
        final_out_csv="out/results.csv",
        final_fail_csv="out/failures.csv",
        page_pause=1.0,
        detail_pause=1.0,
        property_types=list(PROPERTY_TYPES.keys()),
        max_pages_per_combo=None
    )

    # 단일 프로세스 테스트가 필요하면 위 주석처리 후 아래 호출
    # crawl_all_single(headless=False, property_types=[0])