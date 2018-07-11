# DrugLawsuitAlert
[![Build Status](https://travis-ci.org/dabku/DrugLawsuitAlert.svg?branch=master)](https://travis-ci.org/dabku/DrugLawsuitAlert)

DrugLawsuitAlert is a project to monitor several US-based Public Attorneys web pages that specialize in medical lawsuits.
The purpose of this project is to notify my significant other about current ongoing lawsuits to adjust decisions on prescribing medications.

All alerts are posted on [Twitter account][Twitter_Account]. Twitter was chosen as an easy solution for public mobile notifications.

The project was originally running every few days on my computer triggered by Task Scheduler, now it's running on RPi in crontab.

### Used modules
* [SQLAlchemy] - Python SQL toolkit and Object Relational Mapper
* [BeautifulSoup] - HTML Parser used for Web Scraping
* [TwitterAPI] - API for tweeter


### Stored data
In this repository, there are no test files as I consider HTML data as the property of their respective owners. However, it's possible to download them.
The database does not store any descriptions or summaries.
Information stored in the database:
* Drug/Lawsuit name
* Source name
* Source link
* Timestamps

### Usage
As mentioned above, I do not store any webpages, even for test purposes.
Execute to download webpages:
```console
python drugAlert.py -mode UPDATE_TEST_FILES
```
To test the script on pre-downloaded webpages:
```console
python drugAlert.py -mode TEST_FILE
```
To test the script and see what twitter entries will look like:
```console
python drugAlert.py -mode TEST_LIVE
```
To run the script, publish tweets and save timestamps in the database
```console
python drugAlert.py -mode LIVE
```

[Twitter_Account]: <https://twitter.com/LawsuitsBot>
[TwitterAPI]: <https://github.com/geduldig/TwitterAPI/>
[SQLAlchemy]: <https://www.sqlalchemy.org/>
[BeautifulSoup]: <https://www.crummy.com/software/BeautifulSoup/bs4/doc/>