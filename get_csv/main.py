import os
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

load_dotenv()

CSV_URL = os.getenv('CSV_URL')
EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')


def main():
    options = webdriver.ChromeOptions()

    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    driver.get(CSV_URL)

    # lOGIN
    login_input = driver.find_element(
        By.XPATH, '/html/body/div[3]/section[1]/div/div/form/div[1]/div[1]/div/input')

    password_input = driver.find_element(
        By.XPATH, '/html/body/div[3]/section[1]/div/div/form/div[1]/div[2]/div/input')

    submit_button = driver.find_element(
        By.XPATH, '/html/body/div[3]/section[1]/div/div/form/div[2]/button')

    # close_button = driver.find_element(
    #     By.XPATH, '/html/body/div[5]/p[1]/a')

    login_input.send_keys(EMAIL)
    password_input.send_keys(PASSWORD)
    # close_button.click()
    submit_button.click()

    # DOWNLOAD
    element_present = EC.presence_of_element_located(
        (By.XPATH, '/html/body/div[3]/div[1]/div[1]/a'))
    WebDriverWait(driver, 5).until(element_present)

    download_button = driver.find_element(
        By.XPATH, '/html/body/div[3]/div[1]/div[1]/a')
    download_button.click()

    time.sleep(5)

    driver.close()


if __name__ == '__main__':
    main()
