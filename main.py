#coding:UTF-8

#libraries needs to be installed
#selenium, pyyaml, slackclient, bs4, lxml
# and phantomjs

# get ChromeDriver from here
# https://sites.google.com/a/chromium.org/chromedriver/downloads

from __future__ import absolute_import, division, print_function

import sys
import json
import re

import datetime
import time

import urllib

from selenium import webdriver
from selenium.webdriver.support.events import EventFiringWebDriver
from selenium.webdriver.support.events import AbstractEventListener
from selenium.webdriver.support.select import Select

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException

from bs4 import BeautifulSoup
import json
import yaml
import os
from slackclient import SlackClient
from time import sleep

#FOR REAL USE set this to be True to hide Chrome screen
HEADLESSNESS = True

#defalut value
SLACK_TOKEN = ''
SLACK_USER_ID = ''
SLACK_CHANNEL: ''

#loading credentials
args = sys.argv
# credentials_mukai.yaml
with open(args[1],"r") as stream:
    try:
        credentials = yaml.load(stream, Loader=yaml.SafeLoader)
        globals().update(credentials)
    except yaml.YAMLError as exc:
        print(exc)

class ScreenshotListener(AbstractEventListener):
    #count for error screenshots
    exception_screenshot_count = 0

    def on_exception(self, exception, driver):
        screenshot_name = "00_exception_{:0>2}.png".format(ScreenshotListener.exception_screenshot_count)
        ScreenshotListener.exception_screenshot_count += 1
        driver.get_screenshot_as_file(screenshot_name)
        print("Screenshot saved as '%s'" % screenshot_name)

def makeDriver(*, headless=True):
    options = Options()
    if(headless):
        options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,800')
    _driver = webdriver.Chrome(options=options)
    return EventFiringWebDriver(_driver, ScreenshotListener())

def loginJobcan(driver):
    url = JC_URL

    driver.get(url)
    driver.implicitly_wait(5)

    userId_box = driver.find_element_by_name('client_login_id')
    managerId_box = driver.find_element_by_name('client_manager_login_id')
    pass_box = driver.find_element_by_name('client_login_password')
    userId_box.send_keys(JC_LOGINID)
    managerId_box.send_keys(JC_MANAGER_LOGINID)
    pass_box.send_keys(JC_PASSWORD)

    #driver.save_screenshot('0before login.png')
    #print( "saved before login" )

    #login
    driver.find_element_by_css_selector('body > div > div:nth-child(1) > form > div:nth-child(5) > button').click()

    #driver.save_screenshot('1after login.png')
    #print( "saved after login" )
    #print("URL:" + driver.current_url)

    #over-work-table
    ActionChains(driver).move_to_element(driver.find_element_by_css_selector('#adit-manage-step > a')).perform()
    #driver.save_screenshot('2after over-work-table.png')

    #待機が必要なので
    time.sleep(1)
    driver.find_element_by_css_selector('#adit-manage-menu > ul > li:nth-child(3) > dl > dd > ul > li:nth-child(2) > a').click()

    #group_id select
    driver.find_element_by_xpath("//*[@id='group_id']/option[@value=" + JC_GROUPID + "]").click()
    driver.find_element_by_css_selector('#form1 > div.btn-block > a.btn.btn-info').click()
    #driver.save_screenshot('3after over-work-table.png')

    return driver

#残業時間を取得して[{staff:スタッフ, overwork:残業時間, overworktime:残業時間(ソート用)}, ...] の形式で返す
def getOverwork(driver):

    overwork_title = driver.find_element_by_xpath("//*[@id='wrap-basic-shift-table']/h3").text + "（" + "{0:%Y-%m-%d}".format(datetime.datetime.now()) +" 時点）"

    overwork_items = []
    while True:
        driver.implicitly_wait(2)
        trs = driver.find_element_by_xpath("//*[@id='wrap-basic-shift-table']/div").find_elements(By.TAG_NAME, "tr")
        for i in range(1,len(trs)-1):
           tds = trs[i].find_elements(By.TAG_NAME, "td")
           for j in range(0,len(tds)):
               if j < len(tds):
                   #スタッフ
                   if j == 0:
                       staff = tds[j].text
                   #残業時間
                   elif j == 3:
                       overwork = tds[j].text
                       #時間のソート用
                       overworktime = float(re.sub('分','', re.sub('時間 ','.',overwork)))
           overwork_items.append((staff, overwork, overworktime))

        hasnextpage = len(driver.find_element_by_xpath("//*[@id='pager_next']").find_elements(By.TAG_NAME, "a"))

        if hasnextpage:
            driver.find_element_by_xpath("//*[@id='pager_next']/a").click()
        else:
            break

    return overwork_title, overwork_items

################## main starts here ##################################
if __name__ == "__main__":
    print( "【start】" + SLACK_USER_ID + " " + str(datetime.datetime.now()))

    sc = SlackClient(SLACK_TOKEN)

    driver = makeDriver(headless=HEADLESSNESS)
    #print( 'driver created' )

    try:

        loginJobcan(driver)

        overwork_title, overwork_items = getOverwork(driver)

    except:
        print("Unexpected error:", sys.exc_info()[0])
        raise
    finally:
        if HEADLESSNESS:
            driver.quit()

    #　message header
    message = "*" + overwork_title + "*\r\n\r\n"

    # overwork_itemsの残業時間（ソート用）でソート
    overwork_items_sorted = sorted(overwork_items, key=lambda x: x[2], reverse=True)
    for overwork_item in overwork_items_sorted:
        staff, overwork, overworktime = overwork_item
        # 35over emphasis
        if float(overworktime) >= 35:
            message = message + "*%s %s* \r\n" % ('{:　<8}'.format(staff), overwork)
        else:
            message = message + "%s %s \r\n" % ('{:　<8}'.format(staff), overwork)

    sc.api_call(
       "chat.postMessage",
       channel=SLACK_CHANNEL,
       text=message,
       username="jobcan 残業時間一覧",
       user=SLACK_USER_ID
    )
    print( "【end  】" + SLACK_USER_ID + " " + str(datetime.datetime.now()))
