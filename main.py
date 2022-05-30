import glob
import logging
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from functools import reduce
from pathlib import Path
from time import sleep

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart

XPATH_TO_INVOICE_PREVIEW_PRINT_BUTTON = '/html/body/div[4]/div/div[2]/div/div/div/div[1]/form/div[6]/a'

XPATH_TO_FIRST_INVOICE_PREVIEW_LINK = '/html/body/div[4]/div/div[2]/div/div/div/div[1]/form/div[2]/div/div[' \
                                      '2]/div/div/div/div[2]/div/div/div[1]/table/tbody/tr[1]/td[7]/a[1]'

XPATH_TO_FIRST_INVOICE_STATUS_CELL = '/html/body/div[4]/div/div[2]/div/div/div/div[1]/form/div[2]/div/div[' \
                                     '2]/div/div/div/div[2]/div/div/div[1]/table/tbody/tr[1]/td[6]'


def fetch_invoices():
    logging.basicConfig(level=os.getenv('DEBUG', False) and logging.DEBUG or logging.INFO)
    logging.info('Starting export invoice process iFirma -> Rachunki iMoje for user %s' % os.getenv('IFIRMA_USER'))
    downloaded_invoices = download_latest_unpaid_invoice(os.getenv('IFIRMA_USER'), os.getenv('IFIRMA_PASSWORD'))

    if not downloaded_invoices:
        logging.info('No new not paid invoices to be synced, aborting')
        return

    logging.info('Fetched invoices: %s' % reduce(lambda a, b: a + ', ' + b, downloaded_invoices))
    send_email_with_invoices_as_attachment(
        downloaded_invoices,
        os.getenv('TARGET_EMAIL'),
        os.getenv('SMTP_USER'),
        os.getenv('SMTP_PASSWORD'),
        os.getenv('SMTP_EMAIL'),
    )

    remove_invoice_files(downloaded_invoices)
    logging.info('Removed invoices: %s' % reduce(lambda a, b: a + ', ' + b, downloaded_invoices))


def download_latest_unpaid_invoice(ifirma_login,
                                   ifirma_password):
    options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": os.getcwd(),
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')

    driver = webdriver.Chrome(service=Service('/usr/bin/chromedriver'), options=options)
    wait = WebDriverWait(driver, 10)

    driver.get('https://www.ifirma.pl/app')

    driver.find_element(by=By.ID, value='login').send_keys(ifirma_login)
    driver.find_element(by=By.ID, value='password').send_keys(ifirma_password)
    driver.find_element(by=By.ID, value='loginButton').click()
    driver.find_element(by=By.CLASS_NAME, value='ikona-konfiguracja').click()

    invoice_status = wait.until(EC.presence_of_element_located((By.XPATH, XPATH_TO_FIRST_INVOICE_STATUS_CELL)))

    if invoice_status.text.find('opłacona') != -1:
        driver.close()
        return []

    driver.find_element(by=By.XPATH, value=XPATH_TO_FIRST_INVOICE_PREVIEW_LINK).click()

    wait.until(EC.presence_of_element_located((By.XPATH, XPATH_TO_INVOICE_PREVIEW_PRINT_BUTTON))).click()

    invoices = glob.glob('faktura*.pdf')
    while not invoices:
        sleep(1)
        invoices = glob.glob('faktura*.pdf')

    driver.close()

    return invoices


def send_email_with_invoices_as_attachment(invoices, target, login, password, sender_mail):
    smtp = smtplib.SMTP('smtp.emaillabs.net.pl', 587)
    smtp.login(login, password)
    msg = MIMEMultipart()
    msg['To'] = target
    msg['Subject'] = 'Opłata za korzystanie z serwisu ifirma.pl. Login: ' + sender_mail

    for path in invoices:
        part = MIMEBase('application', "octet-stream")
        with open(path, 'rb') as file:
            part.set_payload(file.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition',
                        'attachment; filename={}'.format(Path(path).name))
        msg.attach(part)
        file.close()

    smtp.sendmail(sender_mail, msg['To'], msg.as_string())
    smtp.quit()


def remove_invoice_files(invoices):
    for path in invoices:
        os.unlink(path)


if __name__ == '__main__':
    load_dotenv()
    fetch_invoices()
