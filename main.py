import glob
import logging
import os
import smtplib
import sys
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

def fetch_invoices():
    logging.basicConfig(level=os.getenv('DEBUG', False) and logging.DEBUG or logging.INFO)
    logging.info('Starting export invoice process iFirma -> payappka for user %s' % os.getenv('IFIRMA_USER'))
    downloaded_invoices = download_latest_unpaid_invoice(os.getenv('IFIRMA_USER'), os.getenv('IFIRMA_PASSWORD'))

    if not downloaded_invoices:
        logging.info('No new not paid invoices to be synced, aborting')
        return 1

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

    return 0


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
    driver.add_cookie({'name' : 'ifi_wgmc', 'value' : 'closed'})

    driver.find_element(by=By.ID, value='login').send_keys(ifirma_login)
    driver.find_element(by=By.ID, value='password').send_keys(ifirma_password)
    driver.find_element(by=By.ID, value='loginButton').click()

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.btn-success')))

    if driver.find_element(by=By.CSS_SELECTOR, value='.btn-success').text.find('Opłać') != 0:
        driver.close()
        return []

    driver.find_element(by=By.CSS_SELECTOR, value='a.btn-secondary:nth-child(2)').click()

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
    sys.exit(fetch_invoices())
