from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time


class SRTReservation:
    def __init__(self, headless=False):
        options = webdriver.ChromeOptions()
        options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
        options.add_argument("window-size=1920,1080")
        # options.add_experimental_option("detach", True) # Removed to prevent extra windows
        if headless:
            options.add_argument('--headless=new') # Use new headless mode for better compatibility
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        self.wait = WebDriverWait(self.driver, 10)

    def login(self, srt_id, password):
        self.driver.get("https://etk.srail.kr/cmc/01/selectLoginForm.do?pageId=TK0701000000")
        time.sleep(1) # Wait for page load
        
        self.wait.until(EC.presence_of_element_located((By.ID, "srchDvNm01")))
        self.driver.find_element(By.ID, "srchDvNm01").send_keys(srt_id)
        time.sleep(0.5)
        self.driver.find_element(By.ID, "hmpgPwdCphd01").send_keys(password)
        time.sleep(0.5)
        
        self.driver.find_element(By.CSS_SELECTOR, "input.submit").click()
        time.sleep(2) # Wait for login redirect

    def search_train(self, departure, arrival, date, time_str, adults="1", target_time=None, time_limit=None):
        # Navigate naturally to avoid bot detection
        try:
            # Click the main menu '승차권' (Ticket)
            menu_btn = self.wait.until(EC.element_to_be_clickable((By.ID, "gnb")))
            menu_btn.click()
            time.sleep(0.5)
            
            # Click the sub-menu '일반승차권 조회' (General Ticket)
            sub_menu = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), '일반승차권')]")))
            sub_menu.click()
            time.sleep(1) # Wait for page load
        except Exception as e:
            print(f"Navigation error: {e}")
            # Fallback to direct get if menu fails (though expected to fail bot check)
            self.driver.get("https://etk.srail.kr/hpg/hra/01/selectTicketList.do?pageId=TK0101010000")
        
        self.wait.until(EC.presence_of_element_located((By.ID, "dptRsStnCdNm")))

        # Set Departure
        dpt_stn = self.driver.find_element(By.ID, "dptRsStnCdNm")
        dpt_stn.clear()
        time.sleep(0.2)
        dpt_stn.send_keys(departure)
        time.sleep(0.5)

        # Set Arrival
        arv_stn = self.driver.find_element(By.ID, "arvRsStnCdNm")
        arv_stn.clear()
        time.sleep(0.2)
        arv_stn.send_keys(arrival)
        time.sleep(0.5)

        # Set Date (YYYYMMDD format usually required for value if we script it, 
        # but let's try selecting from dropdown or setting value if it's a select)
        # Based on inspection, date is often a select box #dptDt on the results page? 
        # Actually main page has #cal input, results page has #dptDt select.
        # Let's assume we are on results page URL as per search_train start.
        
        try:
            # Format date to YYYYMMDD
            # date input: "20260217"
            from selenium.webdriver.support.ui import Select
            
            # Select Date
            date_select = Select(self.driver.find_element(By.ID, "dptDt"))
            date_select.select_by_value(date)
            time.sleep(0.2)
            
            # Select Time
            time_select = Select(self.driver.find_element(By.ID, "dptTm"))
            # time_str needs to be even hours usually, e.g., "080000"
            # However, if we utilize a range, we should start searching from the start time
            # The dropdown usually has values like "000000", "020000", ... "220000"
            # We will use the closest even hour before or equal to time_str
            
            start_hour = int(time_str[:2])
            if start_hour % 2 != 0:
                start_hour -= 1 # adjust to even hour for dropdown compatibility if needed
            
            formatted_time_str = f"{start_hour:02d}0000"
            
            time_select.select_by_value(formatted_time_str)
            time.sleep(0.2)
            
            # Select Passengers (pax defaults to 1 if not set, we use arg)
            # On results page, it's a direct dropdown #psgInfoPerPrnb1
            adult_select = Select(self.driver.find_element(By.ID, "psgInfoPerPrnb1"))
            adult_select.select_by_value(str(adults))
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error setting search parameters: {e}")
            return

        attempt_count = 0 
        while True:
            attempt_count += 1
            print(f"\n[시도 {attempt_count}] 기차 조회를 시작합니다...")

            try:
                # 1. Capture old element to check for refresh
                try:
                    old_rows = self.driver.find_elements(By.CSS_SELECTOR, "#search-list tbody tr")
                    old_first_row = old_rows[0] if old_rows else None
                except:
                    old_first_row = None

                # 2. Click Search using JS
                search_btn = self.driver.find_element(By.CLASS_NAME, "inquery_btn")
                self.driver.execute_script("arguments[0].click();", search_btn)
                print(f"[시도 {attempt_count}] 조회 버튼 클릭 완료, 결과 갱신 대기 중...")
                
                # 3. Explicitly wait for the old table to disappear (refresh)
                # This handles "Waiting for connection" popups - script will pause here until update is done.
                if old_first_row:
                    try:
                        WebDriverWait(self.driver, 60).until(EC.staleness_of(old_first_row))
                        print(f"[시도 {attempt_count}] 결과 테이블 갱신 감지됨.")
                    except:
                        print(f"[시도 {attempt_count}] 결과 테이블 갱신 대기 실패 (시간 초과 또는 변경 없음).")

                # 4. Wait for new table to appear
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#search-list tbody tr")))
                time.sleep(0.5)

                rows = self.driver.find_elements(By.CSS_SELECTOR, "#search-list tbody tr")
                
                if not rows:
                     print(f"[시도 {attempt_count}] 조회된 기차가 없습니다. 재시도합니다...")
                     time.sleep(1)
                     continue

                target_found = False
                
                for row in rows:
                    try:
                        dep_time_text = row.find_element(By.CSS_SELECTOR, "td:nth-child(4)").text.strip() # e.g. "07:25" or "수서\n07:25"
                        # Clean up text using regex to find HH:MM
                        import re
                        match = re.search(r"\d{2}:\d{2}", dep_time_text)
                        if match:
                            dep_time_text = match.group()
                        else:
                            # Fallback or skip if no time found
                            continue
                        
                        # Compare time
                        # We need to convert HH:MM to comparable integer or string
                        train_hour = int(dep_time_text.split(":")[0])
                        train_min = int(dep_time_text.split(":")[1])
                        train_time_val = train_hour * 100 + train_min # 725 for 07:25
                        
                        # Parse start time
                        start_h = int(time_str[:2])
                        start_m = int(time_str[2:4])
                        start_val = start_h * 100 + start_m
                        
                        # Check constraints
                        is_after_start = train_time_val >= start_val
                        
                        is_before_limit = True
                        if time_limit:
                            limit_h = int(time_limit[:2])
                            limit_m = int(time_limit[2:4])
                            limit_val = limit_h * 100 + limit_m
                            is_before_limit = train_time_val < limit_val
                            
                        # Specific target check (legacy support)
                        is_target_match = True
                        if target_time:
                             is_target_match = (dep_time_text == target_time)
                        
                        # Logic:
                        # If time_limit is set, we use range [start, limit]
                        # If target_time is set, we use ONLY target_time
                        # If neither, we reserve ANY available (as per original logic "Search ALL")
                        
                        should_reserve = False
                        
                        if target_time:
                            if is_target_match:
                                should_reserve = True
                                print(f"[시도 {attempt_count}] 목표 시간 기차 발견: {dep_time_text}")
                        elif time_limit:
                            if is_after_start and is_before_limit:
                                should_reserve = True
                                print(f"[시도 {attempt_count}] 범위 내 기차 발견: {dep_time_text} (조건: {time_str}-{time_limit})")
                        else:
                            # Original behavior: just check start time? 
                            # If no limit and no target, maybe just reserve first available?
                            # Let's assume start time implies "after this time".
                            if is_after_start:
                                should_reserve = True
                                print(f"[시도 {attempt_count}] 예약 가능 기차 발견: {dep_time_text}")

                        if should_reserve:
                            col_general = row.find_element(By.CSS_SELECTOR, "td:nth-child(7)")
                            try:
                                # Try a more general selector first
                                reserve_anchors = col_general.find_elements(By.TAG_NAME, "a")
                                clicked = False
                                for anchor in reserve_anchors:
                                    if "예약하기" in anchor.text:
                                        print(f"[시도 {attempt_count}] 예약을 시도합니다... (버튼 찾음: {anchor.text})")
                                        anchor.click()
                                        clicked = True
                                        
                                        # Handle potential popup (Native Alert)
                                        try:
                                            WebDriverWait(self.driver, 3).until(EC.alert_is_present())
                                            alert = self.driver.switch_to.alert
                                            print(f"[시도 {attempt_count}] 팝업 감지됨: {alert.text}")
                                            alert.accept()
                                            print(f"[시도 {attempt_count}] 팝업 확인 완료.")
                                        except:
                                            print(f"[시도 {attempt_count}] 팝업 없음.")

                                        print(f"[시도 {attempt_count}] 예약 성공 가능성이 높습니다! 확인 바랍니다.")
                                        return # Success!
                                
                                if not clicked:
                                    print(f"[시도 {attempt_count}] 예약 가능한 기차({dep_time_text})를 발견했으나, '예약하기' 버튼을 찾지 못했습니다. (버튼 텍스트 불일치 또는 비활성화)")
                            
                            except Exception as fail_e:
                                print(f"[시도 {attempt_count}] 예약 버튼 처리 중 에러 발생: {fail_e}")
                                pass
                                
                    except Exception as e:
                        print(f"[시도 {attempt_count}] 행 처리 중 에러 발생: {e}")
                        continue
                
                print(f"[시도 {attempt_count}] 현재 페이지에서 예약 가능한 기차를 찾지 못했습니다. 재시도합니다...")
                time.sleep(0.5) # Short sleep
                
            except Exception as e:
                if "stale element reference" in str(e):
                    continue
                print(f"[시도 {attempt_count}] 에러 발생: {e}")
                time.sleep(1)

    def reserve(self):
        # Logic moved to search_train loop for better flow
        pass

    def close(self):
        # Keep open for verification but quitting for now to prevent multiple sessions if testing repeatedly
        # or user might want to see the result. 
        # For now, let's just pass or quit. User seems to be testing.
        pass

if __name__ == "__main__":
    import os
    # Hardcoded credentials for user convenience in this script run
    srt_id = ""
    srt_pw = ""
    
    srt = SRTReservation()
    srt.login(srt_id, srt_pw)
    
    # Run search loop with Time Range
    # def search_train(self, departure, arrival, date, time_str, adults="1", target_time=None, time_limit=None):
    
    # 1. 수서 -> 동대구, 2026/02/17, 07:00 ~ 09:00, 성인 2명
    srt.search_train(departure="수서", 
                     arrival="동대구", 
                     date="20260217", 
                     time_str="080000", 
                     adults="1", 
                     target_time="08:00"
			)
    
    # 2. 동대구 -> 수서, 2026/02/17, 17:00 ~ 19:00, 성인 2명
    # srt.search_train(departure="동대구", 
    #                  arrival="수서", 
    #                  date="20260217", 
    #                  time_str="170000", 
    #                  adults="1", 
    #                  time_limit="190000")
    
    input("예약이 완료되었습니다. 결제를 진행하고, 종료하려면 엔터를 누르세요...")
