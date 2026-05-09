#!/usr/bin/env python3
"""
Selenium-based stress test for oTree experiment.
Simulates multiple participants navigating through the experiment flow.

Usage:
    python stress_test.py --url <session_url> --participants <number> [--headless] [--delay <seconds>]

Example:
    python stress_test.py --url https://your-app.herokuapp.com/join/abc123 --participants 24 --headless --delay 3
"""

import argparse
import logging
import random
import threading
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException,
    ElementClickInterceptedException, InvalidSessionIdException
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os

# Configure logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.FileHandler(f'stress_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class StressTestBot:
    """
    Bot that simulates a participant navigating through the oTree experiment.
    """
    
    def __init__(self, session_url, participant_id, headless=False, start_delay=0):
        """
        Initialize a stress test bot.
        
        Args:
            session_url: Full URL to join the oTree session
            participant_id: Unique ID for this bot (for logging)
            headless: Run browser in headless mode (no GUI)
            start_delay: Delay before starting (for staggering)
        """
        self.session_url = session_url
        self.participant_id = participant_id
        self.headless = headless
        self.start_delay = start_delay
        self.driver = None
        self.success = False
        self.error_message = None
        self.completed_pages = []
        self.round_stats = {}  # Track stats per round: {round_num: {'goods': X, 'bids': Y, 'asks': Z, 'acceptances': W}}
        self.rounds_processed = set()  # Track which rounds have already been processed to avoid duplicate execution
        
    def setup_browser(self):
        """Initialize the browser session with optimized resource settings."""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument('--headless=new')  # Use new headless mode
            
            # Essential for headless/stability
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            
            # Memory and resource optimizations
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')  # Disable image loading to save memory
            chrome_options.add_argument('--disable-javascript-harmony-shipping')
            chrome_options.add_argument('--disable-background-networking')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-features=TranslateUI')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            
            # Memory limits
            chrome_options.add_argument('--max_old_space_size=512')  # Limit memory per instance
            chrome_options.add_argument('--memory-pressure-off')
            
            # Performance optimizations
            chrome_options.add_argument('--disable-background-downloads')
            chrome_options.add_argument('--disable-client-side-phishing-detection')
            chrome_options.add_argument('--disable-component-update')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--disable-hang-monitor')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-prompt-on-repost')
            chrome_options.add_argument('--disable-sync')
            chrome_options.add_argument('--disable-web-resources')
            chrome_options.add_argument('--metrics-recording-only')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--safebrowsing-disable-auto-update')
            chrome_options.add_argument('--enable-automation')
            chrome_options.add_argument('--password-store=basic')
            chrome_options.add_argument('--use-mock-keychain')
            
            # Disable images and media for memory savings
            prefs = {
                "profile.managed_default_content_settings.images": 2,  # Block images
                "profile.default_content_setting_values.media_stream_mic": 2,
                "profile.default_content_setting_values.media_stream_camera": 2,
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # Set page load strategy to eager (don't wait for all resources)
            
            chrome_options.page_load_strategy = 'eager'
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Set shorter timeouts to fail faster and recover
            self.driver.set_page_load_timeout(60)  # 60s max for page load
            self.driver.implicitly_wait(3)  # Reduced from 5s to 3s
            self.driver.set_script_timeout(30)  # 30s max for JavaScript
            
            logger.info(f"Bot {self.participant_id}: Browser initialized")
            return True
        except Exception as e:
            logger.error(f"Bot {self.participant_id}: Failed to initialize browser: {e}")
            logger.error(f"Bot {self.participant_id}: Error details: {str(e)}")
            return False
    
    def _wait_for_page_load(self, timeout=30):
        """Wait for page to load, with shorter timeout for wait pages."""
        try:
            # Check if we're on a wait page that auto-advances
            current_url = self.driver.current_url
            wait_pages = ['FormTradingGroups', 'WaitingMarket', 'ResultsWaitPage']
            is_wait_page = any(page in current_url for page in wait_pages)
            
            # Use shorter timeout for wait pages (they auto-advance)
            actual_timeout = 10 if is_wait_page else timeout
            
            WebDriverWait(self.driver, actual_timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(0.5)  # Small buffer for dynamic content
            return True
        except TimeoutException:
            if is_wait_page:
                logger.warning(f"Bot {self.participant_id}: Page load timeout (wait page, may auto-advance)")
            else:
                logger.warning(f"Bot {self.participant_id}: Page load timeout")
            return False
        except Exception as e:
            logger.warning(f"Bot {self.participant_id}: Error waiting for page load: {e}")
            return False
    
    def _find_and_click_next(self, timeout=10):
        """Find and click the Next button with robust error handling."""
        selectors = [
            (By.ID, 'participationButton'),  # Instructions page custom button
            (By.NAME, 'isParticipating'),  # Instructions page
            (By.CSS_SELECTOR, 'button[type="submit"]'),  # Generic submit button
            (By.CSS_SELECTOR, 'input[type="submit"]'),  # Generic submit input
            (By.CSS_SELECTOR, '.btn.btn-primary'),  # Bootstrap primary button
            (By.CSS_SELECTOR, '.otree-btn-next'),  # oTree next button
            (By.XPATH, '//button[contains(text(), "Next")]'),  # Button with "Next" text
            (By.XPATH, '//button[contains(text(), "Continue")]'),  # Button with "Continue" text
            (By.XPATH, '//input[@value="Next"]'),  # Input with "Next" value
        ]
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Wait for page to stabilize
                time.sleep(0.5)
                
                # Try each selector
                for by, selector in selectors:
                    try:
                        # Wait for element to be present
                        element = WebDriverWait(self.driver, 2).until(
                            EC.presence_of_element_located((by, selector))
                        )
                        
                        # Wait for element to be clickable
                        element = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((by, selector))
                        )
                        
                        # Scroll into view
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        time.sleep(0.2)
                        
                        # Try regular click first
                        try:
                            element.click()
                            logger.debug(f"Bot {self.participant_id}: Successfully clicked Next using {by}={selector}")
                            time.sleep(0.5)  # Wait for navigation
                            return True
                        except (ElementClickInterceptedException, StaleElementReferenceException) as e:
                            # Fallback to JavaScript click
                            logger.warning(f"Bot {self.participant_id}: Regular click failed, using JavaScript click: {e}")
                            try:
                                self.driver.execute_script("arguments[0].click();", element)
                                time.sleep(0.5)
                                return True
                            except Exception as js_e:
                                logger.warning(f"Bot {self.participant_id}: JavaScript click also failed: {js_e}")
                                continue
                        
                    except (TimeoutException, NoSuchElementException):
                        continue
                
                # If we get here, no selector worked - check if page auto-advanced
                time.sleep(1)
                current_url = self.driver.current_url
                if 'Market' in current_url or 'Results' in current_url or 'Survey' in current_url or 'FinalResults' in current_url:
                    logger.debug(f"Bot {self.participant_id}: Page auto-advanced (no button needed)")
                    return True
                
                if attempt < max_retries - 1:
                    logger.debug(f"Bot {self.participant_id}: Could not find Next button (attempt {attempt + 1}/{max_retries}), retrying...")
                    time.sleep(1)
                
            except Exception as e:
                logger.warning(f"Bot {self.participant_id}: Error finding Next button (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
        
        logger.error(f"Bot {self.participant_id}: Could not find Next button after {max_retries} attempts")
        return False
    
    def _check_for_error_message(self):
        """Check if there's an error message on the page (in newsTable)."""
        try:
            # Check newsTable for error messages
            try:
                news_table = self.driver.find_element(By.ID, 'newsTable')
                news_text = news_table.text.strip()
                if news_text and news_text.lower() not in ['no alerts', '']:
                    # Check if it's an error message (contains words like "cannot", "error", "insufficient", etc.)
                    error_keywords = ['cannot', 'error', 'insufficient', 'misspecified', 'not available', 'better offer']
                    if any(keyword in news_text.lower() for keyword in error_keywords):
                        logger.warning(f"Bot {self.participant_id}: Error message detected: {news_text}")
                        return True
            except NoSuchElementException:
                pass
            
            # Also check for alert-danger elements
            error_selectors = [
                (By.CSS_SELECTOR, '.alert-danger'),
                (By.CSS_SELECTOR, '.error'),
            ]
            for by, selector in error_selectors:
                try:
                    error_element = self.driver.find_element(by, selector)
                    if error_element.is_displayed():
                        error_text = error_element.text.strip()
                        if error_text:
                            logger.warning(f"Bot {self.participant_id}: Error message detected: {error_text}")
                            return True
                except NoSuchElementException:
                    continue
            return False
        except:
            return False
    
    def _get_current_resources(self):
        """Get current cash and assets from the market page."""
        try:
            cash = 0
            assets = 0
            
            # Try to get resources from JavaScript variables or DOM
            cash = self.driver.execute_script("return typeof cash !== 'undefined' ? cash : 0;") or 0
            assets = self.driver.execute_script("return typeof assets !== 'undefined' ? assets : 0;") or 0
            
            # If JavaScript doesn't work, try parsing from DOM
            if cash == 0 or assets == 0:
                try:
                    cash_elem = self.driver.find_element(By.ID, 'cash')
                    cash = float(cash_elem.text.strip())
                except:
                    pass
                
                try:
                    assets_elem = self.driver.find_element(By.ID, 'assets')
                    assets = float(assets_elem.text.strip())
                except:
                    pass
            
            return int(cash), int(assets)
        except Exception as e:
            logger.debug(f"Bot {self.participant_id}: Could not get resources: {e}")
            return 10, 10  # Default fallback
    
    def _select_radio(self, field_name, value):
        """Select a radio button value."""
        try:
            selectors = [
                f"input[name='{field_name}'][value='{value}']",
                f"input[name='{field_name}'][value='{str(value).lower()}']",
                f"input[name='{field_name}'][value='{str(value).upper()}']",
                f"input[id='id_{field_name}_{value}']",
                f"input[id='id_{field_name}_{str(value).lower()}']",
            ]
            
            for selector in selectors:
                try:
                    element = WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if not element.is_selected():
                        self.driver.execute_script("arguments[0].click();", element)
                    return True
                except:
                    continue
            
            return False
        except Exception as e:
            logger.debug(f"Bot {self.participant_id}: Error selecting radio {field_name}={value}: {e}")
            return False
    
    def _verify_radio_selected(self, field_name, value):
        """Verify a radio button is selected."""
        try:
            selectors = [
                f"input[name='{field_name}'][value='{value}']:checked",
                f"input[name='{field_name}'][value='{str(value).lower()}']:checked",
            ]
            for selector in selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.is_selected():
                        return True
                except:
                    continue
            return False
        except:
            return False
    
    def _select_field(self, field_name, value, field_type='auto'):
        """Select a field value (dropdown or radio)."""
        try:
            # Try dropdown first
            try:
                select_elem = self.driver.find_element(By.NAME, field_name)
                if select_elem.tag_name == 'select':
                    from selenium.webdriver.support.ui import Select
                    select = Select(select_elem)
                    select.select_by_value(str(value))
                    time.sleep(0.2)
                    return True
            except:
                pass
            
            # Try radio buttons
            return self._select_radio(field_name, value)
        except Exception as e:
            logger.debug(f"Bot {self.participant_id}: Error selecting field {field_name}={value}: {e}")
            return False
    
    def _verify_field_selected(self, field_name, value):
        """Verify a field (dropdown) is selected."""
        try:
            select_elem = self.driver.find_element(By.NAME, field_name)
            if select_elem.tag_name == 'select':
                from selenium.webdriver.support.ui import Select
                select = Select(select_elem)
                selected_value = select.first_selected_option.get_attribute('value')
                return str(selected_value) == str(value)
            return self._verify_radio_selected(field_name, value)
        except:
            return False
    
    def _fill_survey_attitudes(self):
        """Fill out the SurveyAttitudes form."""
        logger.info(f"Bot {self.participant_id}: Filling SurveyAttitudes form")
        
        fields = {
            'pct_effectiveness': random.randint(2, 4),
            'pct_fairness': random.randint(2, 4),
            'pct_support': random.randint(2, 4),
            'climate_concern': random.randint(3, 5),
            'climate_responsibility': random.randint(2, 4),
        }
        
        try:
            self.driver.find_element(By.NAME, 'co2_certificate_trust')
            bool_value = random.choice([True, False])
            fields['co2_certificate_trust'] = bool_value
            logger.debug(f"Bot {self.participant_id}: Found co2_certificate_trust field (destruction framing)")
        except NoSuchElementException:
            logger.debug(f"Bot {self.participant_id}: co2_certificate_trust field not found (not destruction framing)")
        
        max_retries = 3
        for field_name, value in fields.items():
            success = False
            for attempt in range(max_retries):
                if field_name == 'co2_certificate_trust':
                    for bool_str in [str(value), "1" if value else "0"]:
                        if self._select_radio(field_name, bool_str):
                            if self._verify_radio_selected(field_name, bool_str):
                                success = True
                                logger.debug(f"Bot {self.participant_id}: Selected and verified {field_name} = {bool_str}")
                                break
                else:
                    if self._select_radio(field_name, str(value)):
                        if self._verify_radio_selected(field_name, str(value)):
                            success = True
                            logger.debug(f"Bot {self.participant_id}: Selected and verified {field_name} = {value}")
                            break
                
                if success:
                    break
                
                if not success and attempt < max_retries - 1:
                    logger.warning(f"Bot {self.participant_id}: Failed to select {field_name} = {value} (attempt {attempt + 1}/{max_retries}), retrying...")
                    time.sleep(0.5)
            
            if not success:
                logger.error(f"Bot {self.participant_id}: FAILED to select {field_name} = {value} after {max_retries} attempts")
            time.sleep(random.uniform(0.2, 0.5))
        
        logger.info(f"Bot {self.participant_id}: Completed filling SurveyAttitudes form")
        return True
    
    def _fill_survey_demographics(self):
        """Fill out the SurveyDemographics form."""
        logger.info(f"Bot {self.participant_id}: Filling SurveyDemographics form")
        
        fields = {
            'age': random.randint(25, 65),
            'gender': random.choice(['male', 'female', 'other', 'prefer_not_to_say']),
            'education': random.choice(['no_degree', 'middle_school', 'high_school', 'vocational_training', 'bachelor', 'master', 'doctorate', 'other']),
            'income': random.randint(1, 23),  # Use full range of choices
            'employment': random.choice(['employed_full_time', 'employed_part_time', 'self_employed', 'student', 'unemployed', 'retired', 'stay_at_home_parent', 'other']),
        }
        
        max_retries = 3
        for field_name, value in fields.items():
            success = False
            for attempt in range(max_retries):
                if field_name in ['age', 'income']:  # These are dropdowns
                    if self._select_field(field_name, str(value), 'auto'):
                        if self._verify_field_selected(field_name, str(value)):
                            success = True
                            logger.debug(f"Bot {self.participant_id}: Selected and verified {field_name} = {value}")
                            break
                else:  # These are radio buttons
                    if self._select_radio(field_name, str(value)):
                        if self._verify_radio_selected(field_name, str(value)):
                            success = True
                            logger.debug(f"Bot {self.participant_id}: Selected and verified {field_name} = {value}")
                            break
                
                if success:
                    break
                
                if not success and attempt < max_retries - 1:
                    logger.warning(f"Bot {self.participant_id}: Failed to select {field_name} = {value} (attempt {attempt + 1}/{max_retries}), retrying...")
                    time.sleep(0.5)
            
            if not success:
                logger.error(f"Bot {self.participant_id}: FAILED to select {field_name} = {value} after {max_retries} attempts")
            time.sleep(random.uniform(0.2, 0.5))
        
        logger.info(f"Bot {self.participant_id}: Completed filling SurveyDemographics form")
        return True
    
    def run(self):
        """Main method to run the participant through the experiment."""
        try:
            # Wait for staggered start
            if self.start_delay > 0:
                time.sleep(self.start_delay)
            
            # Setup browser
            if not self.setup_browser():
                self.error_message = "Browser initialization failed"
                return False
            
            # Navigate to session
            logger.info(f"Bot {self.participant_id}: Joining session...")
            self.driver.get(self.session_url)
            self._wait_for_page_load()
            
            # ====================================================================
            # PREPARATION APP PAGES
            # ====================================================================
            
            # Welcome page
            if 'Welcome' in self.driver.current_url or 'welcome' in self.driver.current_url.lower():
                self.completed_pages.append('Welcome')
                logger.info(f"Bot {self.participant_id}: Welcome page")
                time.sleep(0.5)
                if not self._find_and_click_next():
                    raise Exception("Failed to proceed from Welcome")
                self._wait_for_page_load()
            
            # Privacy page
            if 'Privacy' in self.driver.current_url:
                self.completed_pages.append('Privacy')
                logger.info(f"Bot {self.participant_id}: Privacy page")
                time.sleep(0.5)
                
                # Click consent button (not a standard form)
                try:
                    consent_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[name="consent"][value="True"]'))
                    )
                    self.driver.execute_script("arguments[0].click();", consent_button)
                    logger.info(f"Bot {self.participant_id}: Clicked consent button")
                    time.sleep(0.5)
                except:
                    # Try alternative selectors
                    try:
                        consent_button = self.driver.find_element(By.XPATH, '//button[contains(text(), "I consent")]')
                        self.driver.execute_script("arguments[0].click();", consent_button)
                        logger.info(f"Bot {self.participant_id}: Clicked consent button")
                        time.sleep(0.5)
                    except:
                        logger.error(f"Bot {self.participant_id}: Could not find consent button")
                        raise Exception("Failed to proceed from Privacy")
                
                self._wait_for_page_load()
            
            # ProlificID page
            if 'ProlificID' in self.driver.current_url or 'prolific' in self.driver.current_url.lower():
                self.completed_pages.append('ProlificID')
                logger.info(f"Bot {self.participant_id}: ProlificID page")
                time.sleep(0.5)
                
                # Fill in prolific ID field
                try:
                    prolific_id_field = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.NAME, 'prolific_id'))
                    )
                    # Generate exactly 24 characters: "TEST" (4) + "002" (3) + random (17) = 24
                    prolific_id = f"TEST{self.participant_id:03d}" + ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=17))
                    prolific_id_field.clear()
                    prolific_id_field.send_keys(prolific_id)
                    time.sleep(0.3)
                    
                    if not self._find_and_click_next():
                        raise Exception("Failed to proceed from ProlificID")
                except Exception as e:
                    logger.error(f"Bot {self.participant_id}: Error on ProlificID page: {e}")
                    raise Exception("Failed to proceed from ProlificID")
                
                self._wait_for_page_load()
            
            # Instructions page
            if 'Instructions' in self.driver.current_url:
                self.completed_pages.append('Instructions')
                logger.info(f"Bot {self.participant_id}: Instructions page")
                time.sleep(2)  # Give time for page to fully render
                
                # Instructions page uses custom button
                try:
                    button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.ID, 'participationButton'))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
                    time.sleep(0.5)
                    button.click()
                    logger.info(f"Bot {self.participant_id}: Clicked participation button")
                    time.sleep(0.5)
                except:
                    if not self._find_and_click_next():
                        raise Exception("Failed to proceed from Instructions")
                
                self._wait_for_page_load()
            
            # ComprehensionCheck page (may appear multiple times if failed)
            comp_attempts = 0
            max_comp_attempts = 6
            
            while 'ComprehensionCheck' in self.driver.current_url and comp_attempts < max_comp_attempts:
                self.completed_pages.append('ComprehensionCheck')
                logger.info(f"Bot {self.participant_id}: ComprehensionCheck page (attempt {comp_attempts + 1})")
                time.sleep(1)
                
                # Fill in correct answers
                comp_answers = {
                    'comp_q1': 'c',  # Total Score increases from 50 to 85
                    'comp_q2': 'a',  # Total Score decreases from 40 to 30
                    'comp_q3': 'c',  # They do not directly affect Total Score, but needed to buy goods
                }
                
                # Check if comp_q4 and comp_q5 exist (they may be hidden)
                try:
                    self.driver.find_element(By.NAME, 'comp_q4')
                    comp_answers['comp_q4'] = 'b'  # Incorrect (they are transferred)
                except:
                    pass
                
                try:
                    self.driver.find_element(By.NAME, 'comp_q5')
                    comp_answers['comp_q5'] = 'c'  # All get base €1.81, highest in group gets bonus
                except:
                    pass
                
                # Check for comp_q6 (destruction framing)
                try:
                    self.driver.find_element(By.NAME, 'comp_q6')
                    comp_answers['comp_q6'] = 'a'  # Correct - CO2 compensation
                except:
                    pass
                
                # Select answers
                for field_name, value in comp_answers.items():
                    self._select_radio(field_name, value)
                    time.sleep(0.2)
                
                time.sleep(0.5)
                
                if not self._find_and_click_next():
                    raise Exception("Failed to proceed from ComprehensionCheck")
                
                self._wait_for_page_load(10)  # Shorter timeout for feedback page
                comp_attempts += 1
                
                # Check if we're on feedback page (means we failed)
                if 'ComprehensionFeedback' in self.driver.current_url:
                    self.completed_pages.append('ComprehensionFeedback')
                    logger.info(f"Bot {self.participant_id}: ComprehensionFeedback page (attempt {comp_attempts})")
                    time.sleep(1)
                    # Feedback page auto-advances or has continue button
                    time.sleep(3)  # Wait for auto-advance or timer
                    self._find_and_click_next()  # Try clicking continue if available
                    self._wait_for_page_load(10)
                    
                    # Should now be back at ComprehensionCheck or ComprehensionPassed
                    if 'ComprehensionPassed' not in self.driver.current_url:
                        continue  # Try again
                elif 'ComprehensionPassed' in self.driver.current_url:
                    break  # Passed!
            
            if comp_attempts >= max_comp_attempts:
                raise Exception(f"Failed comprehension check after {max_comp_attempts} attempts")
            
            # ComprehensionPassed page
            if 'ComprehensionPassed' in self.driver.current_url:
                self.completed_pages.append('ComprehensionPassed')
                logger.info(f"Bot {self.participant_id}: ComprehensionPassed page")
                time.sleep(2)  # Give time for page to render
                
                # Retry logic for ComprehensionPassed
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        if self._find_and_click_next(timeout=15):
                            break
                        elif retry < max_retries - 1:
                            logger.warning(f"Bot {self.participant_id}: Retry {retry + 1}/{max_retries} on ComprehensionPassed")
                            time.sleep(2)
                    except StaleElementReferenceException:
                        logger.warning(f"Bot {self.participant_id}: Stale element on ComprehensionPassed, retrying...")
                        time.sleep(1)
                        continue
                else:
                    logger.error(f"Bot {self.participant_id}: Failed to proceed from ComprehensionPassed")
                    raise Exception("Failed to proceed from ComprehensionPassed")
                
                self._wait_for_page_load()
            
            # FormTradingGroups page (waiting for group formation)
            if 'FormTradingGroups' in self.driver.current_url:
                self.completed_pages.append('FormTradingGroups')
                logger.info(f"Bot {self.participant_id}: FormTradingGroups page (waiting for group)")
                
                # Wait for auto-advance (page refreshes every 5 seconds)
                start_wait = time.time()
                max_wait = 1800  # 30 minutes max
                
                while 'FormTradingGroups' in self.driver.current_url and (time.time() - start_wait) < max_wait:
                    time.sleep(2)
                    current_url = self.driver.current_url
                    if 'FormTradingGroups' not in current_url:
                        break
                
                if 'FormTradingGroups' in self.driver.current_url:
                    raise Exception("Timeout waiting for group formation")
                
                self._wait_for_page_load()
            
            # ====================================================================
            # TRADING APP PAGES - Multiple rounds
            # ====================================================================
            
            round_num = 1
            max_rounds = 10  # Safety limit - experiment typically has 5 rounds, but allow for more
            
            while round_num <= max_rounds:
                try:
                    current_url = self.driver.current_url
                    
                    # Check if we've reached surveys or final results (end of trading)
                    if 'SurveyAttitudes' in current_url or 'SurveyDemographics' in current_url or 'FinalResults' in current_url:
                        logger.info(f"Bot {self.participant_id}: Reached surveys/final results, ending trading rounds")
                        break
                    
                    # EndOfTrialRounds page (shown after round 1)
                    if 'EndOfTrialRounds' in current_url:
                        self.completed_pages.append(f'EndOfTrialRounds_R{round_num}')
                        logger.info(f"Bot {self.participant_id}: EndOfTrialRounds page (after round {round_num})")
                        
                        # Wait a bit for page to fully load and ensure Next button is available
                        time.sleep(1)  # Reduced initial wait to be faster
                        
                        # Retry logic for EndOfTrialRounds (page has 10s timeout, so need to be quick)
                        max_retries = 8  # More retries for this critical page (increased from 5)
                        success = False
                        for retry in range(max_retries):
                            # Check if page already advanced (timeout happened) - check FIRST before trying to click
                            current_url_check = self.driver.current_url
                            if 'EndOfTrialRounds' not in current_url_check:
                                logger.info(f"Bot {self.participant_id}: EndOfTrialRounds auto-advanced (round {round_num}, retry {retry+1})")
                                success = True
                                break
                            
                            # Try to click Next with shorter timeout per attempt
                            if self._find_and_click_next(timeout=3):  # Reduced timeout per attempt to be faster
                                logger.info(f"Bot {self.participant_id}: Successfully clicked Next on EndOfTrialRounds (round {round_num}, retry {retry+1})")
                                success = True
                                break
                            elif retry < max_retries - 1:
                                logger.warning(f"Bot {self.participant_id}: Retry {retry+1}/{max_retries} on EndOfTrialRounds (round {round_num})")
                                # Check again if page advanced during wait
                                time.sleep(0.5)  # Shorter wait between retries
                                current_url_check = self.driver.current_url
                                if 'EndOfTrialRounds' not in current_url_check:
                                    logger.info(f"Bot {self.participant_id}: EndOfTrialRounds auto-advanced during retry wait (round {round_num})")
                                    success = True
                                    break
                        
                        if not success:
                            # Check one more time if page advanced
                            if 'EndOfTrialRounds' not in self.driver.current_url:
                                logger.info(f"Bot {self.participant_id}: EndOfTrialRounds eventually auto-advanced (round {round_num})")
                                success = True
                        
                        if not success:
                            raise Exception(f"Failed to proceed from EndOfTrialRounds (round {round_num})")
                        
                        self._wait_for_page_load()
                        round_num += 1
                        continue
                    
                    # PreMarket page
                    if 'PreMarket' in current_url:
                        self.completed_pages.append(f'PreMarket_R{round_num}')
                        logger.info(f"Bot {self.participant_id}: PreMarket page (round {round_num})")
                        time.sleep(2)  # Give time for page to render
                        
                        # Check if already advanced
                        time.sleep(0.5)
                        if 'PreMarket' not in self.driver.current_url:
                            logger.info(f"Bot {self.participant_id}: Already advanced from PreMarket (round {round_num}, URL: {self.driver.current_url})")
                        else:
                            # Retry logic for PreMarket
                            max_retries = 3
                            for retry in range(max_retries):
                                if self._find_and_click_next(timeout=15):
                                    logger.info(f"Bot {self.participant_id}: Successfully clicked Next on PreMarket (round {round_num}, attempt {retry + 1})")
                                    break
                                elif retry < max_retries - 1:
                                    logger.warning(f"Bot {self.participant_id}: Retry {retry + 1}/{max_retries} on PreMarket (round {round_num})")
                                    time.sleep(2)
                            else:
                                raise Exception(f"Failed to proceed from PreMarket (round {round_num})")
                        
                        self._wait_for_page_load()
                        continue
                    
                    # WaitingMarket page
                    if 'WaitingMarket' in current_url:
                        self.completed_pages.append(f'WaitingMarket_R{round_num}')
                        logger.info(f"Bot {self.participant_id}: WaitingMarket (waiting for all players, round {round_num})")
                        
                        # Wait for auto-advance (page auto-refreshes)
                        # oTree's WaitingMarket timeout is 180 seconds (3 minutes), so wait at least that long
                        start_wait = time.time()
                        max_wait = 200  # Wait up to 200 seconds (slightly longer than oTree's 180s timeout)
                        while 'WaitingMarket' in self.driver.current_url and (time.time() - start_wait) < max_wait:
                            time.sleep(2)  # Check every 2 seconds instead of every 1 second
                            current_url_check = self.driver.current_url
                            if 'WaitingMarket' not in current_url_check:
                                logger.info(f"Bot {self.participant_id}: WaitingMarket auto-advanced (round {round_num})")
                                break
                        
                        # If still on WaitingMarket after timeout, check if we should proceed
                        if 'WaitingMarket' in self.driver.current_url:
                            logger.warning(f"Bot {self.participant_id}: WaitingMarket timeout after {max_wait}s (round {round_num}), checking if we can proceed...")
                            # Wait longer and check again - oTree times out at 180s, page might need time to refresh
                            time.sleep(10)  # Wait longer for page refresh after timeout
                            # Check current URL
                            current_url_after_timeout = self.driver.current_url
                            if 'WaitingMarket' not in current_url_after_timeout:
                                logger.info(f"Bot {self.participant_id}: WaitingMarket eventually advanced after timeout (round {round_num})")
                            else:
                                # Try refreshing the page once to see if it advances
                                logger.warning(f"Bot {self.participant_id}: Still on WaitingMarket, trying page refresh...")
                                try:
                                    self.driver.refresh()
                                    time.sleep(5)
                                    current_url_after_refresh = self.driver.current_url
                                    if 'WaitingMarket' not in current_url_after_refresh:
                                        logger.info(f"Bot {self.participant_id}: WaitingMarket advanced after refresh (round {round_num})")
                                    else:
                                        logger.error(f"Bot {self.participant_id}: Still on WaitingMarket after refresh (round {round_num}), this may indicate a problem")
                                        raise Exception(f"Stuck on WaitingMarket page after {max_wait}s timeout and refresh (round {round_num})")
                                except Exception as e:
                                    if "Stuck on WaitingMarket" in str(e):
                                        raise
                                    # If refresh failed for other reason, raise the original exception
                                    raise Exception(f"Stuck on WaitingMarket page after {max_wait}s timeout (round {round_num})")
                        
                        self._wait_for_page_load(10)
                        continue
                    
                    # Market page (main trading page)
                    if 'Market' in current_url and 'WaitingMarket' not in current_url:
                        # Check if this round was already processed to avoid infinite loops (check FIRST before anything else)
                        if round_num in self.rounds_processed:
                            # Round already processed - wait briefly and continue (page will advance eventually)
                            # Don't add to completed_pages or log anything - just wait for page to advance
                            time.sleep(2)  # Wait for page to advance
                            continue
                        
                        # Check if we've already logged this Market page for this round (avoid duplicates from page refreshes)
                        # IMPORTANT: Check completed_pages BEFORE adding, to prevent duplicates
                        market_page_key = f'Market_R{round_num}'
                        
                        # Only add to completed_pages and log if we haven't already
                        if market_page_key not in self.completed_pages:
                            # First time seeing Market page for this round - log and add to completed_pages ONCE
                            self.completed_pages.append(market_page_key)
                            logger.info(f"Bot {self.participant_id}: Market page (trading, round {round_num})")
                        # If already in completed_pages, skip logging (avoid log spam) but still play round
                        # _play_market_round will check if round is already processed and skip if so
                        
                        # Play the market round
                        self._play_market_round(round_num)
                        continue
                    
                    # ResultsWaitPage
                    if 'ResultsWaitPage' in current_url:
                        self.completed_pages.append(f'ResultsWaitPage_R{round_num}')
                        logger.info(f"Bot {self.participant_id}: ResultsWaitPage (round {round_num})")
                        
                        # Wait for auto-advance
                        start_wait = time.time()
                        while 'ResultsWaitPage' in self.driver.current_url and (time.time() - start_wait) < 30:
                            time.sleep(1)
                            if 'ResultsWaitPage' not in self.driver.current_url:
                                logger.info(f"Bot {self.participant_id}: ResultsWaitPage auto-advanced (round {round_num})")
                                break
                        
                        self._wait_for_page_load(10)
                        continue
                    
                    # Results page
                    if 'Results' in current_url and 'ResultsWaitPage' not in current_url and 'FinalResults' not in current_url:
                        self.completed_pages.append(f'Results_R{round_num}')
                        logger.info(f"Bot {self.participant_id}: Results page (round {round_num})")
                        time.sleep(1)
                        
                        # Retry logic for Results page
                        max_retries = 3
                        for retry in range(max_retries):
                            if self._find_and_click_next(timeout=15):
                                logger.info(f"Bot {self.participant_id}: Successfully clicked Next on Results (round {round_num}, attempt {retry + 1})")
                                break
                            elif retry < max_retries - 1:
                                logger.warning(f"Bot {self.participant_id}: Retry {retry + 1}/{max_retries} on Results (round {round_num})")
                                time.sleep(2)
                        else:
                            raise Exception(f"Failed to proceed from Results (round {round_num})")
                        
                        self._wait_for_page_load()
                        
                        # Check if next round or end
                        current_url = self.driver.current_url
                        if 'EndOfTrialRounds' in current_url:
                            continue  # Will be handled in next iteration
                        elif 'PreMarket' in current_url:
                            round_num += 1
                            logger.info(f"Bot {self.participant_id}: Starting main round {round_num}")
                            continue
                        elif 'SurveyAttitudes' in current_url or 'SurveyDemographics' in current_url or 'FinalResults' in current_url:
                            break  # End of trading rounds
                        else:
                            round_num += 1
                            continue
                    
                    # If we get here, check if we've moved to a new page type
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Bot {self.participant_id}: Error in round {round_num}: {e}")
                    raise
            
            # ====================================================================
            # SURVEY PAGES
            # ====================================================================
            
            # SurveyAttitudes
            if 'SurveyAttitudes' in self.driver.current_url:
                self.completed_pages.append('SurveyAttitudes')
                logger.info(f"Bot {self.participant_id}: SurveyAttitudes page")
                time.sleep(1)
                
                if self._fill_survey_attitudes():
                    time.sleep(0.5)
                    if not self._find_and_click_next():
                        raise Exception("Failed to proceed from SurveyAttitudes")
                
                self._wait_for_page_load()
            
            # SurveyDemographics
            if 'SurveyDemographics' in self.driver.current_url:
                self.completed_pages.append('SurveyDemographics')
                logger.info(f"Bot {self.participant_id}: SurveyDemographics page")
                time.sleep(1)
                
                if self._fill_survey_demographics():
                    time.sleep(0.5)
                    if not self._find_and_click_next():
                        raise Exception("Failed to proceed from SurveyDemographics")
                
                self._wait_for_page_load()
            
            # ====================================================================
            # FINAL RESULTS PAGE
            # ====================================================================
            
            # FinalResults page
            if 'FinalResults' in self.driver.current_url:
                self.completed_pages.append('FinalResults')
                logger.info(f"Bot {self.participant_id}: FinalResults page")
                
                # Verify we're actually on FinalResults
                time.sleep(2)
                final_url = self.driver.current_url
                if 'FinalResults' not in final_url:
                    logger.error(f"Bot {self.participant_id}: Expected FinalResults page but found: {final_url}")
                    raise Exception(f"Expected FinalResults page but found: {final_url}")
                
                self.success = True
                logger.info(f"Bot {self.participant_id}: Completed successfully! (reached FinalResults)")
                return True
            elif 'Results' in self.driver.current_url and round_num >= max_rounds:
                # If we've reached max rounds and are on Results, this might be the final Results page
                logger.info(f"Bot {self.participant_id}: Reached max rounds ({max_rounds}) on Results page. This may be the final Results page.")
                # Wait a bit to see if page advances to FinalResults
                time.sleep(3)
                final_url_check = self.driver.current_url
                if 'FinalResults' in final_url_check:
                    logger.info(f"Bot {self.participant_id}: Page advanced to FinalResults")
                    self.success = True
                    return True
                elif 'Results' in final_url_check and 'Market' not in final_url_check:
                    # If still on Results (but not Market), this is likely the final Results page
                    logger.info(f"Bot {self.participant_id}: Completed experiment (reached final Results page after {max_rounds} rounds)")
                    self.success = True
                    return True
                else:
                    logger.error(f"Bot {self.participant_id}: Did not reach expected end state after max rounds. Current URL: {final_url_check}")
                    self.error_message = f"Did not reach FinalResults. Last URL: {final_url_check}"
                    return False
            else:
                logger.error(f"Bot {self.participant_id}: Did not reach FinalResults page. Current URL: {self.driver.current_url}")
                self.error_message = f"Did not reach FinalResults. Last URL: {self.driver.current_url}"
                return False
                
        except InvalidSessionIdException as e:
            logger.error(f"Bot {self.participant_id}: Browser session lost: {e}")
            self.error_message = f"Invalid session id: {e}"
            return False
        except Exception as e:
            logger.error(f"Bot {self.participant_id}: Error in run(): {e}")
            self.error_message = str(e)
            return False
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
    
    def _post_bid(self, round_num, max_retries=10):
        """Post a bid: enter value 0.5-3.0, click post bid button. Retry if fails."""
        bid_price = round(random.uniform(0.5, 3.0), 2)
        for attempt in range(max_retries):
            try:
                # Find input field and enter price
                input_field = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.ID, 'limitBidPrice'))
                )
                input_field.clear()
                time.sleep(0.1)
                input_field.send_keys(str(bid_price))
                time.sleep(0.2)
                
                # Click post bid button
                button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.ID, 'bidOffer'))
                )
                self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
                time.sleep(0.1)
                button.click()
                
                # Wait longer for server response
                time.sleep(1.2)
                
                # Check for error message
                if self._check_for_error_message():
                    logger.debug(f"Bot {self.participant_id}: Round {round_num} - Bid rejected by server (attempt {attempt+1}), retrying...")
                    time.sleep(0.5)
                    continue
                
                # Verify bid appears in table (wait a bit more for update)
                time.sleep(0.3)
                my_id = self.driver.execute_script("return typeof js_vars !== 'undefined' ? js_vars.id_in_group : null;")
                bids_rows = self.driver.find_elements(By.CSS_SELECTOR, '#bidsTable tbody tr')
                for row in bids_rows:
                    try:
                        row_id = row.get_attribute('data-value')
                        if row_id and str(row_id) == str(my_id):
                            # Our bid appears in the table - success!
                            logger.info(f"Bot {self.participant_id}: Round {round_num} - Posted bid at {bid_price:.2f}")
                            return True
                    except:
                        continue
                
                # Bid doesn't appear yet, might need more time
                logger.debug(f"Bot {self.participant_id}: Round {round_num} - Bid not yet visible (attempt {attempt+1}), retrying...")
                time.sleep(0.5)
            except Exception as e:
                logger.debug(f"Bot {self.participant_id}: Error posting bid (attempt {attempt+1}): {e}")
                time.sleep(0.5)
        return False
    
    def _post_ask(self, round_num, max_retries=10):
        """Post an ask: enter value 3.0-5.0, click post ask button. Retry if fails."""
        ask_price = round(random.uniform(3.0, 5.0), 2)
        for attempt in range(max_retries):
            try:
                # Find input field and enter price
                input_field = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.ID, 'limitAskPrice'))
                )
                input_field.clear()
                time.sleep(0.1)
                input_field.send_keys(str(ask_price))
                time.sleep(0.2)
                
                # Click post ask button
                button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.ID, 'SendOffer'))
                )
                self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
                time.sleep(0.1)
                button.click()
                
                # Wait longer for server response
                time.sleep(1.2)
                
                # Check for error message
                if self._check_for_error_message():
                    logger.debug(f"Bot {self.participant_id}: Round {round_num} - Ask rejected by server (attempt {attempt+1}), retrying...")
                    time.sleep(0.5)
                    continue
                
                # Verify ask appears in table (wait a bit more for update)
                time.sleep(0.3)
                my_id = self.driver.execute_script("return typeof js_vars !== 'undefined' ? js_vars.id_in_group : null;")
                asks_rows = self.driver.find_elements(By.CSS_SELECTOR, '#asksTable tbody tr')
                for row in asks_rows:
                    try:
                        row_id = row.get_attribute('data-value')
                        if row_id and str(row_id) == str(my_id):
                            # Our ask appears in the table - success!
                            logger.info(f"Bot {self.participant_id}: Round {round_num} - Posted ask at {ask_price:.2f}")
                            return True
                    except:
                        continue
                
                # Ask doesn't appear yet, might need more time
                logger.debug(f"Bot {self.participant_id}: Round {round_num} - Ask not yet visible (attempt {attempt+1}), retrying...")
                time.sleep(0.5)
            except Exception as e:
                logger.debug(f"Bot {self.participant_id}: Error posting ask (attempt {attempt+1}): {e}")
                time.sleep(0.5)
        return False
    
    def _accept_order(self, round_num, max_retries=3):
        """Accept a bid or ask: use JavaScript directly to select and accept the topmost order. Max 3 retries."""
        for attempt in range(max_retries):
            try:
                # Wait for table to update
                time.sleep(0.3)
                
                # Get current resources (all bots have both cash and assets)
                cash, assets = self._get_current_resources()
                
                # Use JavaScript to get the first order and accept it directly via liveSend
                # Randomly choose between asks and bids (50/50) since all bots have both cash and assets
                prefer_bid = random.choice([True, False])
                
                # Build JavaScript code with random choice
                js_code = f"""
                    var targetRow = null;
                    var isBid = null;
                    var my_id = typeof js_vars !== 'undefined' ? js_vars.id_in_group : null;
                    var preferBid = {str(prefer_bid).lower()};
                    
                    // Randomly try bids first or asks first (50/50)
                    if (preferBid) {{
                        // Try bids first (selling)
                        var bidsRows = document.querySelectorAll('#bidsTable tbody tr');
                        for (var i = 0; i < bidsRows.length; i++) {{
                            var row = bidsRows[i];
                            var row_id = row.getAttribute('data-value');
                            if (row_id && parseInt(row_id) !== parseInt(my_id)) {{
                                targetRow = row;
                                isBid = 1;
                                break;
                            }}
                        }}
                        // If no bid, try asks
                        if (!targetRow) {{
                            var asksRows = document.querySelectorAll('#asksTable tbody tr');
                            for (var i = 0; i < asksRows.length; i++) {{
                                var row = asksRows[i];
                                var row_id = row.getAttribute('data-value');
                                if (row_id && parseInt(row_id) !== parseInt(my_id)) {{
                                    targetRow = row;
                                    isBid = 0;
                                    break;
                                }}
                            }}
                        }}
                    }} else {{
                        // Try asks first (buying)
                        var asksRows = document.querySelectorAll('#asksTable tbody tr');
                        for (var i = 0; i < asksRows.length; i++) {{
                            var row = asksRows[i];
                            var row_id = row.getAttribute('data-value');
                            if (row_id && parseInt(row_id) !== parseInt(my_id)) {{
                                targetRow = row;
                                isBid = 0;
                                break;
                            }}
                        }}
                        // If no ask, try bids
                        if (!targetRow) {{
                            var bidsRows = document.querySelectorAll('#bidsTable tbody tr');
                            for (var i = 0; i < bidsRows.length; i++) {{
                                var row = bidsRows[i];
                                var row_id = row.getAttribute('data-value');
                                if (row_id && parseInt(row_id) !== parseInt(my_id)) {{
                                    targetRow = row;
                                    isBid = 1;
                                    break;
                                }}
                            }}
                        }}
                    }}
                    
                    if (!targetRow) {{
                        return {{success: false, reason: 'no_other_orders'}};
                    }}
                    
                    // Get offerID and price from the row
                    var offerID = targetRow.getAttribute('value');
                    var priceCell = targetRow.querySelector('td:last-child');
                    var price = priceCell ? priceCell.getAttribute('value') : null;
                    
                    if (!offerID || !price) {{
                        return {{success: false, reason: 'missing_data'}};
                    }}
                    
                    // Call liveSend directly with the order data
                    if (typeof liveSend !== 'undefined') {{
                        liveSend({{
                            'operationType': 'market_order',
                            'offerID': parseInt(offerID),
                            'isBid': isBid,
                            'transactionPrice': parseFloat(price),
                            'transactionVolume': 1
                        }});
                    }} else {{
                        return {{success: false, reason: 'liveSend_not_found'}};
                    }}
                    
                    return {{success: true, offerID: offerID, price: price, isBid: isBid}};
                """
                
                result = self.driver.execute_script(js_code)
                
                if not result or not result.get('success'):
                    reason = result.get('reason', 'unknown') if result else 'unknown'
                    logger.warning(f"Bot {self.participant_id}: Round {round_num} - No order available (attempt {attempt+1}): {reason}")
                    time.sleep(0.5)
                    continue
                
                order_type = 'bid' if result.get('isBid') == 1 else 'ask'
                logger.info(f"Bot {self.participant_id}: Round {round_num} - Attempting to accept {order_type} (offerID={result.get('offerID')}, attempt {attempt+1})")
                
                # Wait for server response and check if it worked
                time.sleep(2.0)  # Wait longer for server response
                
                # Check for errors
                if self._check_for_error_message():
                    logger.warning(f"Bot {self.participant_id}: Round {round_num} - Accept failed (attempt {attempt+1}), retrying...")
                    time.sleep(0.5)
                    continue
                
                # Success! (if no error message, assume it worked)
                logger.info(f"Bot {self.participant_id}: Round {round_num} - Accepted {order_type} (offerID={result.get('offerID')})")
                return True  # STOP after first successful acceptance - only 1 per round!
                
            except Exception as e:
                logger.warning(f"Bot {self.participant_id}: Error accepting order (attempt {attempt+1}): {e}")
                time.sleep(0.5)
        
        # Failed after max_retries - return False so bot can proceed to goods buying
        logger.warning(f"Bot {self.participant_id}: Round {round_num} - Could not accept order after {max_retries} attempts, will proceed to goods buying")
        return False
    
    def _play_market_round(self, round_num):
        """Play a market round: post bid, post ask, accept order, then buy goods."""
        # Prevent duplicate execution for the same round (can happen with page refreshes)
        if round_num in self.rounds_processed:
            logger.debug(f"Bot {self.participant_id}: Round {round_num} already processed, skipping")
            return
        
        try:
            start_market = time.time()
            max_market_time = 210
            goods_bought = 0
            bids_posted = 0
            asks_posted = 0
            orders_accepted = 0
            
            # Initialize stats if not already set
            if round_num not in self.round_stats:
                self.round_stats[round_num] = {'goods': 0, 'bids': 0, 'asks': 0, 'acceptances': 0}
            
            logger.info(f"Bot {self.participant_id}: Round {round_num} - Starting market trading")
            
            # Wait a bit for market to initialize
            time.sleep(2)
            
            # PHASE 1: Post bid, post ask, then accept order immediately after both are posted (max 70 seconds)
            phase1_end = start_market + 60  # Max 60 seconds for Phase 1, leaving 20 seconds for goods buying
            while time.time() < phase1_end:
                # Check if market ended
                if 'Market' not in self.driver.current_url:
                    break
                
                # Post bid (once, keep retrying)
                if bids_posted == 0:
                    if self._post_bid(round_num, max_retries=5):
                        bids_posted = 1
                    time.sleep(0.2)  # Reduced wait
                
                # Post ask (once, keep retrying, wait a bit after bid)
                if asks_posted == 0 and bids_posted == 1 and time.time() - start_market >= 1.5:  # Reduced wait
                    if self._post_ask(round_num, max_retries=5):
                        asks_posted = 1
                    time.sleep(0.2)  # Reduced wait
                
                # Accept order IMMEDIATELY after both bid and ask are posted - try 3 times, then proceed to goods
                if bids_posted == 1 and asks_posted == 1 and orders_accepted == 0:
                    # Try to accept an order - only 3 retries, then proceed to goods buying
                    if self._accept_order(round_num, max_retries=3):
                        orders_accepted = 1
                        logger.info(f"Bot {self.participant_id}: Round {round_num} - Successfully accepted order, moving to goods buying")
                        break  # Once accepted, move to Phase 2 immediately
                    else:
                        # After 3 failed attempts, proceed to goods buying anyway
                        logger.info(f"Bot {self.participant_id}: Round {round_num} - Could not accept order after 3 attempts, proceeding to goods buying")
                        break
                
                # If we've accepted, break to move to Phase 2
                if orders_accepted == 1:
                    break
                
                time.sleep(0.1)  # Reduced wait
            
            logger.info(f"Bot {self.participant_id}: Round {round_num} - Phase 1 complete: Bids={bids_posted}, Asks={asks_posted}, Acceptances={orders_accepted}")
            
            # PHASE 2: Buy goods (remaining time, start immediately after acceptance) - stop after 5 goods
            # Start buying goods immediately after acceptance, or at latest at 60 seconds
            logger.info(f"Bot {self.participant_id}: Round {round_num} - Starting Phase 2: Buying goods")
            while time.time() - start_market < max_market_time and goods_bought < 5:  # Stop after buying 5 goods
                # Check if market ended
                if 'Market' not in self.driver.current_url:
                    logger.info(f"Bot {self.participant_id}: Round {round_num} - Market ended, stopping goods buying")
                    break
                
                # Alternate between Good A and Good B
                good_choice = 'A' if (goods_bought % 2 == 0) else 'B'
                
                # Click buy button directly - no affordability check
                try:
                    button_id = f'buy{good_choice}_btn'
                    logger.info(f"Bot {self.participant_id}: Round {round_num} - Attempting to buy Good {good_choice} (attempt {goods_bought + 1})")
                    
                    buy_button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.ID, button_id))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", buy_button)
                    time.sleep(0.1)
                    buy_button.click()
                    time.sleep(0.6)  # Wait for server response
                    
                    if not self._check_for_error_message():
                        goods_bought += 1
                        logger.info(f"Bot {self.participant_id}: Round {round_num} - Bought Good {good_choice} (total: {goods_bought})")
                        # Update stats immediately (using max to prevent overwriting)
                        if round_num not in self.round_stats:
                            self.round_stats[round_num] = {'goods': 0, 'bids': 0, 'asks': 0, 'acceptances': 0}
                        self.round_stats[round_num]['goods'] = max(self.round_stats[round_num]['goods'], goods_bought)
                        # Stop after buying 5 goods
                        if goods_bought >= 5:
                            logger.info(f"Bot {self.participant_id}: Round {round_num} - Reached 5 goods, stopping goods buying")
                            break
                    else:
                        logger.warning(f"Bot {self.participant_id}: Round {round_num} - Good {good_choice} purchase failed (error message detected)")
                    time.sleep(0.2)  # Wait between purchase attempts
                except Exception as e:
                    logger.warning(f"Bot {self.participant_id}: Error buying good {good_choice}: {e}")
                    time.sleep(0.3)  # Wait before retry
            
            # Update stats (only if higher than previous to avoid overwriting with lower values)
            if round_num not in self.round_stats:
                self.round_stats[round_num] = {'goods': 0, 'bids': 0, 'asks': 0, 'acceptances': 0}
            
            # Only update if values are higher (to prevent overwriting with 0 from duplicate calls)
            self.round_stats[round_num]['goods'] = max(self.round_stats[round_num]['goods'], goods_bought)
            self.round_stats[round_num]['bids'] = max(self.round_stats[round_num]['bids'], bids_posted)
            self.round_stats[round_num]['asks'] = max(self.round_stats[round_num]['asks'], asks_posted)
            self.round_stats[round_num]['acceptances'] = max(self.round_stats[round_num]['acceptances'], orders_accepted)
            
            # Mark round as processed
            self.rounds_processed.add(round_num)
            
            logger.info(f"Bot {self.participant_id}: Round {round_num} complete - Goods: {goods_bought}, Bids: {bids_posted}, Asks: {asks_posted}, Acceptances: {orders_accepted}")
            
        except Exception as e:
            logger.error(f"Bot {self.participant_id}: Error in _play_market_round (round {round_num}): {e}")
            # Mark as processed even on error to prevent infinite retry loops
            self.rounds_processed.add(round_num)


def run_stress_test(session_url, num_participants, headless=False, stagger_delay=2):
    """
    Run the stress test with multiple bot participants.
    
    Args:
        session_url: Full URL to join the oTree session
        num_participants: Number of bot participants to create
        headless: Run browsers in headless mode
        stagger_delay: Delay between starting each bot (seconds)
    
    Returns:
        Dictionary with test results
    """
    logger.info(f"Starting stress test with {num_participants} participants")
    logger.info(f"Session URL: {session_url}")
    
    bots = []
    threads = []
    start_time = time.time()
    
    # Create and start bots with staggered delays
    for i in range(1, num_participants + 1):
        bot = StressTestBot(
            session_url=session_url,
            participant_id=i,
            headless=headless,
            start_delay=i * stagger_delay  # Stagger starts
        )
        bots.append(bot)
        
        thread = threading.Thread(target=bot.run)
        thread.daemon = True
        thread.start()
        threads.append(thread)
        
        # Small delay between thread starts to avoid overwhelming system
        time.sleep(0.1)
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join(timeout=3600)  # 1 hour max per bot
    
    duration = time.time() - start_time
    
    # Collect results
    successful = sum(1 for bot in bots if bot.success)
    failed = num_participants - successful
    
    # Print results
    logger.info(f"\n{'='*60}")
    logger.info(f"STRESS TEST RESULTS")
    logger.info(f"{'='*60}")
    logger.info(f"Total participants: {num_participants}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    logger.info(f"Success rate: {successful/num_participants*100:.1f}%")
    
    # Aggregate and display per-round statistics
    if successful > 0:
        logger.info(f"\nPer-Round Trading Statistics (averaged across {successful} successful bots):")
        all_round_numbers = sorted(list(set(r_num for bot in bots if bot.success for r_num in bot.round_stats.keys())))
        
        if all_round_numbers:
            logger.info(f"{'Round':<8} {'Goods Bought':<15} {'Bids Posted':<13} {'Asks Posted':<13} {'Orders Accepted':<16}")
            logger.info(f"{'-'*8:<8} {'-'*15:<15} {'-'*13:<13} {'-'*13:<13} {'-'*16:<16}")
            
            for r_num in all_round_numbers:
                total_goods = sum(bot.round_stats.get(r_num, {}).get('goods', 0) for bot in bots if bot.success)
                total_bids = sum(bot.round_stats.get(r_num, {}).get('bids', 0) for bot in bots if bot.success)
                total_asks = sum(bot.round_stats.get(r_num, {}).get('asks', 0) for bot in bots if bot.success)
                total_acceptances = sum(bot.round_stats.get(r_num, {}).get('acceptances', 0) for bot in bots if bot.success)
                
                avg_goods = total_goods / successful
                avg_bids = total_bids / successful
                avg_asks = total_asks / successful
                avg_acceptances = total_acceptances / successful
                
                logger.info(f"{r_num:<8} {avg_goods:<15.1f} {avg_bids:<13.1f} {avg_asks:<13.1f} {avg_acceptances:<16.1f}")
        else:
            logger.info("No round statistics available.")
    
    # List failed bots
    failed_bots = [bot for bot in bots if not bot.success]
    if failed_bots:
        logger.info(f"\nFailed bots:")
        for bot in failed_bots:
            logger.info(f"  Bot {bot.participant_id}: {bot.error_message}")
            logger.info(f"    Pages completed: {', '.join(bot.completed_pages)}")
    
    return {
        'total': num_participants,
        'successful': successful,
        'failed': failed,
        'duration': duration,
        'success_rate': successful/num_participants*100 if num_participants > 0 else 0,
        'round_stats': {r_num: {
            'goods_bought': sum(bot.round_stats.get(r_num, {}).get('goods', 0) for bot in bots if bot.success) / successful,
            'bids_posted': sum(bot.round_stats.get(r_num, {}).get('bids', 0) for bot in bots if bot.success) / successful,
            'asks_posted': sum(bot.round_stats.get(r_num, {}).get('asks', 0) for bot in bots if bot.success) / successful,
            'orders_accepted': sum(bot.round_stats.get(r_num, {}).get('acceptances', 0) for bot in bots if bot.success) / successful
        } for r_num in all_round_numbers} if successful > 0 and all_round_numbers else {}
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Stress test oTree experiment with Selenium bots')
    parser.add_argument('--url', type=str, required=True, help='Full session URL to join (e.g., https://app.herokuapp.com/join/abc123)')
    parser.add_argument('--participants', type=int, required=True, help='Number of bot participants')
    parser.add_argument('--headless', action='store_true', help='Run browsers in headless mode')
    parser.add_argument('--delay', type=float, default=2, help='Delay between starting each bot (seconds, default: 2)')
    
    args = parser.parse_args()
    
    results = run_stress_test(
        session_url=args.url,
        num_participants=args.participants,
        headless=args.headless,
        stagger_delay=args.delay
    )
    
    # Exit with error code if any bots failed
    exit(0 if results['failed'] == 0 else 1)

