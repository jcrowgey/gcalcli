#!/usr/bin/env python3
import json
import locale
import os
import random
import re
import shlex
import sys
import textwrap
import time
from datetime import date, datetime, timedelta
from unicodedata import east_asian_width
from argparse import Namespace

from gcalcli import (__API_CLIENT_ID__, __API_CLIENT_SECRET__, __program__,
                     __version__, colors)
from gcalcli import cli
from gcalcli.utils import DateTimeParser, days_since_epoch, get_time_from_str


# Required 3rd party libraries
try:
    from dateutil.tz import tzlocal
    from dateutil.parser import parse
    import httplib2
    from apiclient.discovery import build
    from apiclient.errors import HttpError
    from oauth2client.file import Storage
    from oauth2client.client import OAuth2WebServerFlow
    from oauth2client.tools import run_flow
except ImportError as e:
    print("ERROR: Missing module - {}".format(e.args[0]))
    sys.exit(1)


# cPickle is a standard library, but in case someone did something really
# dumb, fall back to pickle.  If that's not there, your python is fucked
try:
    import cPickle as pickle
except ImportError:
    import pickle


locale.setlocale(locale.LC_ALL, "")


def setup_run_flow_flags():
    flags = Namespace()
    flags.logging_level = 'INFO'
    flags.noauth_local_webserver = True
    flags.auth_host_port = [8080, 8090]
    flags.auth_host_name = 'localhost'
    return flags


class ART:

    useArt = True
    fancy = ''
    plain = ''

    def __str__(self):
        return self.fancy if self.useArt else self.plain


class ART_HRZ(ART):
    fancy = '\033(0\x71\033(B'
    plain = '-'


class ART_VRT(ART):
    fancy = '\033(0\x78\033(B'
    plain = '|'


class ART_LRC(ART):
    fancy = '\033(0\x6A\033(B'
    plain = '+'


class ART_URC(ART):
    fancy = '\033(0\x6B\033(B'
    plain = '+'


class ART_ULC(ART):
    fancy = '\033(0\x6C\033(B'
    plain = '+'


class ART_LLC(ART):
    fancy = '\033(0\x6D\033(B'
    plain = '+'


class ART_CRS(ART):
    fancy = '\033(0\x6E\033(B'
    plain = '+'


class ART_LTE(ART):
    fancy = '\033(0\x74\033(B'
    plain = '+'


class ART_RTE(ART):
    fancy = '\033(0\x75\033(B'
    plain = '+'


class ART_BTE(ART):
    fancy = '\033(0\x76\033(B'
    plain = '+'


class ART_UTE(ART):
    fancy = '\033(0\x77\033(B'
    plain = '+'


class GoogleCalendarInterface:

    cache = {}
    all_cals = []
    allEvents = []
    cals = []
    now = datetime.now(tzlocal())
    agendaLength = 5
    maxRetries = 5
    authHttp = None
    cal_service = None
    url_service = None
    command = 'notify-send -u critical -a gcalcli %s'
    date_parser = DateTimeParser()

    ACCESS_OWNER = 'owner'
    ACCESS_WRITER = 'writer'
    ACCESS_READER = 'reader'
    ACCESS_FREEBUSY = 'freeBusyReader'

    UNIWIDTH = {'W': 2, 'F': 2, 'N': 1, 'Na': 1, 'H': 1, 'A': 1}

    def __init__(self,
                 cal_names=[],
                 cal_name_colors=[],
                 military=False,
                 detail_calendar=False,
                 detail_location=False,
                 detail_attendees=False,
                 detail_attachments=False,
                 detail_length=False,
                 detail_reminder=False,
                 detail_descr=False,
                 detail_descr_width=80,
                 detail_url=None,
                 detail_email=False,
                 ignore_started=False,
                 ignoreDeclined=False,
                 calWidth=10,
                 calMonday=False,
                 calOwnerColor=colors.CLR_CYN(),
                 calWriterColor=colors.CLR_GRN(),
                 calReaderColor=colors.CLR_MAG(),
                 calFreeBusyColor=colors.CLR_NRM(),
                 date_color=colors.CLR_YLW(),
                 nowMarkerColor=colors.CLR_BRRED(),
                 border_color=colors.CLR_WHT(),
                 tsv=False,
                 refresh_cache=False,
                 use_cache=True,
                 config_folder=None,
                 client_id=__API_CLIENT_ID__,
                 client_secret=__API_CLIENT_SECRET__,
                 defaultReminders=False,
                 all_day=False):

        self.military = military
        self.ignore_started = ignore_started
        self.ignoreDeclined = ignoreDeclined
        self.calWidth = calWidth
        self.calMonday = calMonday
        self.tsv = tsv
        self.refresh_cache = refresh_cache
        self.use_cache = use_cache
        self.defaultReminders = defaultReminders
        self.all_day = all_day

        self.detail_calendar = detail_calendar
        self.detail_location = detail_location
        self.detail_length = detail_length
        self.detail_reminder = detail_reminder
        self.detail_descr = detail_descr
        self.detail_descr_width = detail_descr_width
        self.detail_url = detail_url
        self.detail_attendees = detail_attendees
        self.detail_attachments = detail_attachments
        self.detail_email = detail_email

        self.calOwnerColor = calOwnerColor
        self.calWriterColor = calWriterColor
        self.calReaderColor = calReaderColor
        self.calFreeBusyColor = calFreeBusyColor
        self.date_color = date_color
        self.nowMarkerColor = nowMarkerColor
        self.border_color = border_color

        self.config_folder = config_folder

        self.client_id = client_id
        self.client_secret = client_secret

        self._get_cached()

        if len(cal_names):
            # Changing the order of this and the `cal in self.all_cals` loop
            # is necessary for the matching to actually be sane (ie match
            # supplied name to cached vs matching cache against supplied names)
            for i in range(len(cal_names)):
                matches = []
                for cal in self.all_cals:
                    # For exact match, we should match only 1 entry and accept
                    # the first entry.  Should honor access role order since
                    # it happens after _get_cached()
                    if cal_names[i] == cal['summary']:
                        # This makes sure that if we have any regex matches
                        # that we toss them out in favor of the specific match
                        matches = [cal]
                        cal['colorSpec'] = cal_name_colors[i]
                        break
                    # Otherwise, if the calendar matches as a regex, append
                    # it to the list of potential matches
                    elif re.search(cal_names[i], cal['summary'], flags=re.I):
                        matches.append(cal)
                        cal['colorSpec'] = cal_name_colors[i]
                # Add relevant matches to the list of calendars we want to
                # operate against
                self.cals += matches
        else:
            self.cals = self.all_cals

    @staticmethod
    def _LocalizeDateTime(dt):
        if not hasattr(dt, 'tzinfo'):
            return dt
        if dt.tzinfo is None:
            return dt.replace(tzinfo=tzlocal())
        else:
            return dt.astimezone(tzlocal())

    def _retry_with_backoff(self, method):
        for n in range(0, self.maxRetries):
            try:
                return method.execute()
            except HttpError as e:
                error = json.loads(e.content)
                if error.get('code') == '403' and \
                        error.get('errors')[0].get('reason') \
                        in ['rateLimitExceeded', 'userRateLimitExceeded']:
                    time.sleep((2 ** n) + random.random())
                else:
                    raise

        return None

    def _GoogleAuth(self):
        if not self.authHttp:
            if self.config_folder:
                storage = Storage(os.path.expanduser("%s/oauth" %
                                                     self.config_folder))
            else:
                storage = Storage(os.path.expanduser('~/.gcalcli_oauth'))

            credentials = storage.get()

            if credentials is None or credentials.invalid:
                flags = setup_run_flow_flags()
                credentials = run_flow(
                    OAuth2WebServerFlow(
                        client_id=self.client_id,
                        client_secret=self.client_secret,
                        scope=['https://www.googleapis.com/auth/calendar',
                               'https://www.googleapis.com/auth/urlshortener'],
                        user_agent=__program__ + '/' + __version__),
                    storage, flags)

            self.authHttp = credentials.authorize(httplib2.Http())

        return self.authHttp

    def _cal_service(self):
        if not self.cal_service:
            self.cal_service = \
                build(serviceName='calendar',
                      version='v3',
                      http=self._GoogleAuth())

        return self.cal_service

    def _url_service(self):
        if not self.url_service:
            self._GoogleAuth()
            self.url_service = \
                build(serviceName='urlshortener',
                      version='v1',
                      http=self._GoogleAuth())

        return self.url_service

    def _get_cached(self):
        if self.config_folder:
            cache_file = os.path.expanduser("%s/cache" % self.config_folder)
        else:
            cache_file = os.path.expanduser('~/.gcalcli_cache')

        if self.refresh_cache:
            try:
                os.remove(cache_file)
            except OSError:
                pass
                # fall through

        self.cache = {}
        self.all_cals = []

        if self.use_cache:
            # note that we need to use pickle for cache data since we stuff
            # various non-JSON data in the runtime storage structures
            try:
                with open(cache_file, 'rb') as _cache_:
                    self.cache = pickle.load(_cache_)
                    self.all_cals = self.cache['all_cals']
                # XXX assuming data is valid, need some verification check here
                return
            except IOError:
                pass
                # fall through

        cal_list = self._retry_with_backoff(
            self._cal_service().calendarList().list())

        while True:
            for cal in cal_list['items']:
                self.all_cals.append(cal)
            pageToken = cal_list.get('nextPageToken')
            if pageToken:
                cal_list = self._retry_with_backoff(
                    self._cal_service().calendar_list().list(
                        pageToken=pageToken))
            else:
                break

        # gcalcli defined way to order calendars
        order = {self.ACCESS_OWNER: 1,
                 self.ACCESS_WRITER: 2,
                 self.ACCESS_READER: 3,
                 self.ACCESS_FREEBUSY: 4}

        self.all_cals.sort(key=lambda x: order[x['accessRole']])

        if self.use_cache:
            self.cache['all_cals'] = self.all_cals
            with open(cache_file, 'wb') as _cache_:
                pickle.dump(self.cache, _cache_)

    def _ShortenURL(self, url):
        if self.detail_url != "short":
            return url
        # Note that when authenticated to a google account different shortUrls
        # can be returned for the same longUrl. See: http://goo.gl/Ya0A9
        shortUrl = self._retry_with_backoff(
            self._url_service().url().insert(body={'longUrl': url}))
        return shortUrl['id']

    def _calendar_color(self, cal):

        if cal is None:
            return colors.CLR_NRM()
        elif 'colorSpec' in cal and cal['colorSpec'] is not None:
            return cal['colorSpec']
        elif cal['accessRole'] == self.ACCESS_OWNER:
            return self.calOwnerColor
        elif cal['accessRole'] == self.ACCESS_WRITER:
            return self.calWriterColor
        elif cal['accessRole'] == self.ACCESS_READER:
            return self.calReaderColor
        elif cal['accessRole'] == self.ACCESS_FREEBUSY:
            return self.calFreeBusyColor
        else:
            return colors.CLR_NRM()

    def _ValidTitle(self, event):
        if 'summary' in event and event['summary'].strip():
            return event['summary']
        else:
            return "(No title)"

    def _is_all_day(self, event):
        return event['s'].hour == 0 and event['s'].minute == 0 and \
                        event['e'].hour == 0 and event['e'].minute == 0

    def _GetWeekEventStrings(self, cmd, curMonth,
                             startDateTime, endDateTime, event_list):

        weekEventStrings = ['', '', '', '', '', '', '']

        nowMarkerPrinted = False
        if self.now < startDateTime or self.now > endDateTime:
            # now isn't in this week
            nowMarkerPrinted = True

        for event in event_list:

            if cmd == 'calm' and curMonth != event['s'].strftime("%b"):
                continue

            dayNum = int(event['s'].strftime("%w"))
            if self.calMonday:
                dayNum -= 1
                if dayNum < 0:
                    dayNum = 6

            if event['s'] >= startDateTime and event['s'] < endDateTime:

                forceEventColorAsMarker = False

                all_day = self._is_all_day(event)

                if not nowMarkerPrinted:
                    if (days_since_epoch(self.now) <
                            days_since_epoch(event['s'])):
                        nowMarkerPrinted = True
                        weekEventStrings[dayNum - 1] += \
                            ("\n" +
                             str(self.nowMarkerColor) +
                             (self.calWidth * '-'))
                    elif self.now <= event['s']:
                        # add a line marker before next event
                        nowMarkerPrinted = True
                        weekEventStrings[dayNum] += \
                            ("\n" +
                             str(self.nowMarkerColor) +
                             (self.calWidth * '-'))
                    # We don't want to recolor all day events, but ignoring
                    # them leads to issues where the "now" marker misprints
                    # into the wrong day.  This resolves the issue by skipping
                    # all day events for specific coloring but not for previous
                    # or next events
                    elif self.now >= event['s'] and \
                            self.now <= event['e'] and \
                            not all_day:
                        # line marker is during the event (recolor event)
                        nowMarkerPrinted = True
                        forceEventColorAsMarker = True

                if all_day:
                    tmp_time_str = ''
                elif self.military:
                    tmp_time_str = event['s'].strftime("%H:%M")
                else:
                    tmp_time_str = \
                        event['s'].strftime("%I:%M").lstrip('0') + \
                        event['s'].strftime('%p').lower()

                if forceEventColorAsMarker:
                    event_color = self.nowMarkerColor
                else:
                    event_color = self._calendar_color(event['gcalcli_cal'])

                # newline and empty string are the keys to turn off coloring
                weekEventStrings[dayNum] += \
                    "\n" + \
                    str(event_color) + \
                    tmp_time_str.strip() + \
                    " " + \
                    self._ValidTitle(event).strip()

        return weekEventStrings

    def _PrintLen(self, string):
        # deprecated: figure out if we have the same issues in py3
        # We need to treat everything as unicode for this to actually give
        # us the info we want.  Date string were coming in as `str` type
        # so we convert them to unicode and then check their size. Fixes
        # the output issues we were seeing around non-US locale strings
        printLen = 0
        for tmpChar in string:
            printLen += self.UNIWIDTH[east_asian_width(tmpChar)]
        return printLen

    # return print length before cut, cut index, and force cut flag
    def _NextCut(self, string, curPrintLen):
        idx = 0
        printLen = 0
        for tmpChar in string:
            if (curPrintLen + printLen) >= self.calWidth:
                return (printLen, idx, True)
            if tmpChar in (' ', '\n'):
                return (printLen, idx, False)
            idx += 1
            printLen += self.UNIWIDTH[east_asian_width(tmpChar)]
        return (printLen, -1, False)

    def _GetCutIndex(self, eventString):

        printLen = self._PrintLen(eventString)

        if printLen <= self.calWidth:
            if '\n' in eventString:
                idx = eventString.find('\n')
                printLen = self._PrintLen(eventString[:idx])
            else:
                idx = len(eventString)

            cli.debug_print("------ printLen=%d (end of string)\n" % idx)
            return (printLen, idx)

        cutWidth, cut, forceCut = self._NextCut(eventString, 0)
        cli.debug_print(
                "------ cutWidth=%d cut=%d \"%s\"\n" % (
                    cutWidth, cut, eventString))

        if forceCut:
            cli.debug_print(
                    "--- forceCut cutWidth=%d cut=%d\n" % (cutWidth, cut))
            return (cutWidth, cut)

        cli.debug_print("--- looping\n")

        while cutWidth < self.calWidth:

            cli.debug_print("--- cutWidth=%d cut=%d \"%s\"\n" % (
                cutWidth, cut, eventString[cut:]))

            while cut < self.calWidth and \
                    cut < printLen and \
                    eventString[cut] == ' ':
                cli.debug_print("-> skipping space <-\n")
                cutWidth += 1
                cut += 1

            cli.debug_print("--- cutWidth=%d cut=%d \"%s\"\n" % (
                cutWidth, cut, eventString[cut:]))

            nextCutWidth, nextCut, forceCut = \
                self._NextCut(eventString[cut:], cutWidth)

            if forceCut:
                cli.debug_print("--- forceCut cutWidth=%d cut=%d\n" % (
                    cutWidth, cut))
                break

            cutWidth += nextCutWidth
            cut += nextCut

            if eventString[cut] == '\n':
                break

            cli.debug_print("--- loop cutWidth=%d cut=%d\n" % (cutWidth, cut))

        return (cutWidth, cut)

    def _graph_events(self, cmd, startDateTime, count, event_list):

        # ignore started events (i.e. events that start previous day and end
        # start day)
        while (len(event_list) and event_list[0]['s'] < startDateTime):
            event_list = event_list[1:]

        dayWidthLine = (self.calWidth * str(ART_HRZ()))

        topWeekDivider = (str(self.border_color) +
                          str(ART_ULC()) + dayWidthLine +
                          (6 * (str(ART_UTE()) + dayWidthLine)) +
                          str(ART_URC()) + str(colors.CLR_NRM()))

        midWeekDivider = (str(self.border_color) +
                          str(ART_LTE()) + dayWidthLine +
                          (6 * (str(ART_CRS()) + dayWidthLine)) +
                          str(ART_RTE()) + str(colors.CLR_NRM()))

        botWeekDivider = (str(self.border_color) +
                          str(ART_LLC()) + dayWidthLine +
                          (6 * (str(ART_BTE()) + dayWidthLine)) +
                          str(ART_LRC()) + str(colors.CLR_NRM()))

        empty = self.calWidth * ' '

        # Get the localized day names... January 1, 2001 was a Monday
        dayNames = [date(2001, 1, i + 1).strftime('%A') for i in range(7)]
        dayNames = dayNames[6:] + dayNames[:6]

        dayHeader = str(self.border_color) + str(ART_VRT()) + str(
                colors.CLR_NRM())
        for i in range(7):
            if self.calMonday:
                if i == 6:
                    dayName = dayNames[0]
                else:
                    dayName = dayNames[i + 1]
            else:
                dayName = dayNames[i]
            dayName += ' ' * (self.calWidth - self._PrintLen(dayName))
            dayHeader += str(self.date_color) + dayName + str(colors.CLR_NRM())
            dayHeader += str(self.border_color) + str(ART_VRT()) + \
                str(colors.CLR_NRM())

        if cmd == 'calm':
            topMonthDivider = (str(self.border_color) +
                               str(ART_ULC()) + dayWidthLine +
                               (6 * (str(ART_HRZ()) + dayWidthLine)) +
                               str(ART_URC()) + str(colors.CLR_NRM()))
            cli.print_msg(colors.CLR_NRM(), "\n" + topMonthDivider + "\n")

            m = startDateTime.strftime('%B %Y')
            mw = (self.calWidth * 7) + 6
            m += ' ' * (mw - self._PrintLen(m))
            cli.print_msg(colors.CLR_NRM(),
                          str(self.border_color) +
                          str(ART_VRT()) +
                          str(colors.CLR_NRM()) +
                          str(self.date_color) +
                          m +
                          str(colors.CLR_NRM()) +
                          str(self.border_color) +
                          str(ART_VRT()) +
                          str(colors.CLR_NRM()) +
                          '\n')

            botMonthDivider = (str(self.border_color) +
                               str(ART_LTE()) + dayWidthLine +
                               (6 * (str(ART_UTE()) + dayWidthLine)) +
                               str(ART_RTE()) + str(colors.CLR_NRM()))
            cli.print_msg(colors.CLR_NRM(), botMonthDivider + "\n")

        else:  # calw
            cli.print_msg(colors.CLR_NRM(), "\n" + topWeekDivider + "\n")

        cli.print_msg(colors.CLR_NRM(), dayHeader + "\n")
        cli.print_msg(colors.CLR_NRM(), midWeekDivider + "\n")

        curMonth = startDateTime.strftime("%b")

        # get date range objects for the first week
        if cmd == 'calm':
            dayNum = int(startDateTime.strftime("%w"))
            if self.calMonday:
                dayNum -= 1
                if dayNum < 0:
                    dayNum = 6
            startDateTime = (startDateTime - timedelta(days=dayNum))
        startWeekDateTime = startDateTime
        endWeekDateTime = (startWeekDateTime + timedelta(days=7))

        for i in range(count):

            # create/print date line
            line = str(self.border_color) + str(ART_VRT()) + str(
                    colors.CLR_NRM())
            for j in range(7):
                if cmd == 'calw':
                    d = (startWeekDateTime +
                         timedelta(days=j)).strftime("%d %b")
                else:  # (cmd == 'calm'):
                    d = (startWeekDateTime +
                         timedelta(days=j)).strftime("%d")
                    if curMonth != (startWeekDateTime +
                                    timedelta(days=j)).strftime("%b"):
                        d = ''
                tmpDateColor = self.date_color

                if self.now.strftime("%d%b%Y") == \
                   (startWeekDateTime + timedelta(days=j)).strftime("%d%b%Y"):
                    tmpDateColor = self.nowMarkerColor
                    d += " **"

                d += ' ' * (self.calWidth - self._PrintLen(d))
                line += str(tmpDateColor) + \
                    d + \
                    str(colors.CLR_NRM()) + \
                    str(self.border_color) + \
                    str(ART_VRT()) + \
                    str(colors.CLR_NRM())
            cli.print_msg(colors.CLR_NRM(), line + "\n")

            weekColorStrings = ['', '', '', '', '', '', '']
            weekEventStrings = self._GetWeekEventStrings(cmd, curMonth,
                                                         startWeekDateTime,
                                                         endWeekDateTime,
                                                         event_list)

            # get date range objects for the next week
            startWeekDateTime = endWeekDateTime
            endWeekDateTime = (endWeekDateTime + timedelta(days=7))

            while True:
                done = True
                line = str(self.border_color) + str(ART_VRT()) + str(
                        colors.CLR_NRM())

                for j in range(7):
                    if weekEventStrings[j] == '':
                        weekColorStrings[j] = ''
                        line += (empty +
                                 str(self.border_color) +
                                 str(ART_VRT()) +
                                 str(colors.CLR_NRM()))
                        continue

                    # get/skip over a color sequence
                    if (not colors.CLR.conky and
                            weekEventStrings[j][0] == '\033') or \
                       (colors.CLR.conky and weekEventStrings[j][0] == '$'):
                        weekColorStrings[j] = ''
                        while (not colors.CLR.conky and
                                weekEventStrings[j][0] != 'm') or \
                              (colors.CLR.conky and
                               weekEventStrings[j][0] != '}'):
                            weekColorStrings[j] += weekEventStrings[j][0]
                            weekEventStrings[j] = weekEventStrings[j][1:]
                        weekColorStrings[j] += weekEventStrings[j][0]
                        weekEventStrings[j] = weekEventStrings[j][1:]

                    if weekEventStrings[j][0] == '\n':
                        weekColorStrings[j] = ''
                        weekEventStrings[j] = weekEventStrings[j][1:]
                        line += (empty +
                                 str(self.border_color) +
                                 str(ART_VRT()) +
                                 str(colors.CLR_NRM()))
                        done = False
                        continue

                    weekEventStrings[j] = weekEventStrings[j].lstrip()

                    printLen, cut = self._GetCutIndex(weekEventStrings[j])
                    padding = ' ' * (self.calWidth - printLen)

                    line += (weekColorStrings[j] +
                             weekEventStrings[j][:cut] +
                             padding +
                             str(colors.CLR_NRM()))
                    weekEventStrings[j] = weekEventStrings[j][cut:]

                    done = False
                    line += (str(self.border_color) +
                             str(ART_VRT()) +
                             str(colors.CLR_NRM()))

                if done:
                    break

                cli.print_msg(colors.CLR_NRM(), line + "\n")

            if i < range(count)[len(range(count)) - 1]:
                cli.print_msg(colors.CLR_NRM(), midWeekDivider + "\n")
            else:
                cli.print_msg(colors.CLR_NRM(), botWeekDivider + "\n")

    def _tsv(self, startDateTime, event_list):
        for event in event_list:
            if self.ignore_started and (event['s'] < self.now):
                continue
            output = "%s\t%s\t%s\t%s" % (event['s'].strftime('%Y-%m-%d'),
                                         event['s'].strftime('%H:%M'),
                                         event['e'].strftime('%Y-%m-%d'),
                                         event['e'].strftime('%H:%M'))

            if self.detail_url:
                output += "\t%s" % (self._ShortenURL(event['htmlLink'])
                                    if 'htmlLink' in event else '')
                output += "\t%s" % (self._ShortenURL(event['hangoutLink'])
                                    if 'hangoutLink' in event else '')

            output += "\t%s" % self._ValidTitle(event).strip()

            if self.detail_location:
                output += "\t%s" % (event['location'].strip()
                                    if 'location' in event else '')

            if self.detail_descr:
                output += "\t%s" % (event['description'].strip()
                                    if 'description' in event else '')

            if self.detail_calendar:
                output += "\t%s" % event['gcalcli_cal']['summary'].strip()

            if self.detail_email:
                output += "\t%s" % (event['creator']['email'].strip()
                                    if 'email' in event['creator'] else '')

            output = "%s\n" % output.replace('\n', '''\\n''')
            sys.stdout.write(output)

    def _print_event(self, event, prefix):

        def _formatDescr(descr, indent, box):
            wrapper = textwrap.TextWrapper()
            if box:
                wrapper.initial_indent = (indent + '  ')
                wrapper.subsequent_indent = (indent + '  ')
                wrapper.width = (self.detail_descr_width - 2)
            else:
                wrapper.initial_indent = indent
                wrapper.subsequent_indent = indent
                wrapper.width = self.detail_descr_width
            new_descr = ""
            for line in descr.split("\n"):
                if box:
                    tmpLine = wrapper.fill(line)
                    for singleLine in tmpLine.split("\n"):
                        singleLine = singleLine.ljust(self.detail_descr_width,
                                                      ' ')
                        new_descr += singleLine[:len(indent)] + \
                            str(ART_VRT()) + \
                            singleLine[(len(indent) + 1):
                                       (self.detail_descr_width - 1)] + \
                            str(ART_VRT()) + '\n'
                else:
                    new_descr += wrapper.fill(line) + "\n"
            return new_descr.rstrip()

        indent = 10 * ' '
        detailsIndent = 19 * ' '

        if self.military:
            timeFormat = '%-5s'
            tmp_time_str = event['s'].strftime("%H:%M")
        else:
            timeFormat = '%-7s'
            tmp_time_str = \
                event['s'].strftime("%I:%M").lstrip('0').rjust(5) + \
                event['s'].strftime('%p').lower()

        if not prefix:
            prefix = indent

        cli.print_msg(self.date_color, prefix)

        happeningNow = event['s'] <= self.now <= event['e']
        all_day = self._is_all_day(event)
        event_color = self.nowMarkerColor if happeningNow and not all_day \
            else self._calendar_color(event['gcalcli_cal'])

        if all_day:
            fmt = '  ' + timeFormat + '  %s\n'
            cli.print_msg(event_color, fmt % (
                '', self._ValidTitle(event).strip()))
        else:
            fmt = '  ' + timeFormat + '  %s\n'
            cli.print_msg(
                    event_color, fmt % (
                        tmp_time_str, self._ValidTitle(event).strip()))

        if self.detail_calendar:
            xstr = "%s  Calendar: %s\n" % (
                detailsIndent,
                event['gcalcli_cal']['summary']
            )
            cli.print_msg(colors.CLR_NRM(), xstr)

        if self.detail_url and 'htmlLink' in event:
            hLink = self._ShortenURL(event['htmlLink'])
            xstr = "%s  Link: %s\n" % (detailsIndent, hLink)
            cli.print_msg(colors.CLR_NRM(), xstr)

        if self.detail_url and 'hangoutLink' in event:
            hLink = self._ShortenURL(event['hangoutLink'])
            xstr = "%s  Hangout Link: %s\n" % (detailsIndent, hLink)
            cli.print_msg(colors.CLR_NRM(), xstr)

        if self.detail_location and \
           'location' in event and \
           event['location'].strip():
            xstr = "%s  Location: %s\n" % (
                detailsIndent,
                event['location'].strip()
            )
            cli.print_msg(colors.CLR_NRM(), xstr)

        if self.detail_attendees and 'attendees' in event:
            xstr = "%s  Attendees:\n" % (detailsIndent)
            cli.print_msg(colors.CLR_NRM(), xstr)

            if 'self' not in event['organizer']:
                xstr = "%s    %s: <%s>\n" % (
                    detailsIndent,
                    event['organizer'].get('displayName', 'Not Provided')
                                      .strip(),
                    event['organizer'].get('email', 'Not Provided').strip()
                )
                cli.print_msg(colors.CLR_NRM(), xstr)

            for attendee in event['attendees']:
                if 'self' not in attendee:
                    xstr = "%s    %s: <%s>\n" % (
                        detailsIndent,
                        attendee.get('displayName', 'Not Provided').strip(),
                        attendee.get('email', 'Not Provided').strip()
                    )
                    cli.print_msg(colors.CLR_NRM(), xstr)

        if self.detail_attachments and 'attachments' in event:
            xstr = "%s  Attachments:\n" % (detailsIndent)
            cli.print_msg(colors.CLR_NRM(), xstr)

            for attendee in event['attachments']:
                xstr = "%s    %s\n%s    -> %s\n" % (
                    detailsIndent,
                    attendee.get('title', 'Not Provided').strip(),
                    detailsIndent,
                    attendee.get('fileUrl', 'Not Provided').strip()
                )
                cli.print_msg(colors.CLR_NRM(), xstr)

        if self.detail_length:
            diffDateTime = (event['e'] - event['s'])
            xstr = "%s  Length: %s\n" % (detailsIndent, diffDateTime)
            cli.print_msg(colors.CLR_NRM(), xstr)

        if self.detail_reminder and 'reminders' in event:
            if event['reminders']['useDefault'] is True:
                xstr = "%s  Reminder: (default)\n" % (detailsIndent)
                cli.print_msg(colors.CLR_NRM(), xstr)
            elif 'overrides' in event['reminders']:
                for rem in event['reminders']['overrides']:
                    xstr = "%s  Reminder: %s %d minutes\n" % \
                           (detailsIndent, rem['method'], rem['minutes'])
                    cli.print_msg(colors.CLR_NRM(), xstr)

        if self.detail_email and \
           'email' in event['creator'] and \
           event['creator']['email'].strip():
            xstr = "%s  Email: %s\n" % (
                detailsIndent,
                event['creator']['email'].strip()
            )
            cli.print_msg(colors.CLR_NRM(), xstr)

        if self.detail_descr and \
           'description' in event and \
           event['description'].strip():
            descrIndent = detailsIndent + '  '
            box = True  # leave old non-box code for option later
            if box:
                topMarker = (descrIndent +
                             str(ART_ULC()) +
                             (str(ART_HRZ()) *
                              ((self.detail_descr_width - len(descrIndent)) -
                               2)) +
                             str(ART_URC()))
                botMarker = (descrIndent +
                             str(ART_LLC()) +
                             (str(ART_HRZ()) *
                              ((self.detail_descr_width - len(descrIndent)) -
                               2)) +
                             str(ART_LRC()))
                xstr = "%s  Description:\n%s\n%s\n%s\n" % (
                    detailsIndent,
                    topMarker,
                    _formatDescr(event['description'].strip(),
                                 descrIndent, box),
                    botMarker
                )
            else:
                marker = descrIndent + '-' * \
                    (self.detail_descr_width - len(descrIndent))
                xstr = "%s  Description:\n%s\n%s\n%s\n" % (
                    detailsIndent,
                    marker,
                    _formatDescr(event['description'].strip(),
                                 descrIndent, box),
                    marker
                )
            cli.print_msg(colors.CLR_NRM(), xstr)

    def _delete_event(self, event):

        if self.iamaExpert:
            self._retry_with_backoff(
                self._cal_service().events().
                delete(calendarId=event['gcalcli_cal']['id'],
                       eventId=event['id']))
            cli.print_msg(colors.CLR_RED(), "Deleted!\n")
            return

        cli.print_msg(colors.CLR_MAG(), "Delete? [N]o [y]es [q]uit: ")
        val = input()

        if not val or val.lower() == 'n':
            return

        elif val.lower() == 'y':
            self._retry_with_backoff(
                self._cal_service().events().
                delete(calendarId=event['gcalcli_cal']['id'],
                       eventId=event['id']))
            cli.print_msg(colors.CLR_RED(), "Deleted!\n")

        elif val.lower() == 'q':
            sys.stdout.write('\n')
            sys.exit(0)

        else:
            cli.print_err_msg('Error: invalid input\n')
            sys.stdout.write('\n')
            sys.exit(1)

    def _date_time_tz_dict(self, date=None, dt=None, tz=None):
        return {'date': date, 'dateTime': dt, 'timeZone': tz}

    def _set_event_start_end(self, new_start, new_end, event):
        event['s'] = parse(new_start)
        event['e'] = parse(new_end)

        if self.all_day:
            event['start'] = self._date_dt_tz_dict(date=new_start)
            event['end'] = self._date_dt_tz_dict(date=new_end)
        else:
            event['start'] = self._date_dt_tz_dict(
                    dt=new_start, tz=event['gcalcli_cal']['timeZone'])
            event['end'] = self._date_dt_tz_dict(
                    dt=new_end, tz=event['gcalcli_cal']['timeZone'])
        return event

    def _edit_event(self, event):

        while True:
            cli.print_msg(colors.CLR_MAG(), "Edit?\n" +
                                            "[N]o [s]ave [q]uit " +
                                            "[t]itle [l]ocation " +
                                            "[w]hen len[g]th " +
                                            "[r]eminder [d]escr: ")
            val = input()

            if not val or val.lower() == 'n':
                return

            elif val.lower() == 's':
                # copy only editable event details for patching
                mod_event = {}
                keys = ['summary', 'location', 'start', 'end',
                        'reminders', 'description']
                for k in keys:
                    if k in event:
                        mod_event[k] = event[k]

                self._retry_with_backoff(
                    self._cal_service().events().
                    patch(calendarId=event['gcalcli_cal']['id'],
                          eventId=event['id'],
                          body=mod_event))
                cli.print_msg(colors.CLR_RED(), "Saved!\n")
                return

            elif not val or val.lower() == 'q':
                sys.stdout.write('\n')
                sys.exit(0)

            elif val.lower() == 't':
                cli.print_msg(colors.CLR_MAG(), "Title: ")
                val = input()
                if val.strip():
                    event['summary'] = val.strip()

            elif val.lower() == 'l':
                cli.print_msg(colors.CLR_MAG(), "Location: ")
                val = input()
                if val.strip():
                    event['location'] = val.strip()

            elif val.lower() == 'w':
                cli.print_msg(colors.CLR_MAG(), "When: ")
                val = input()
                if val.strip():
                    td = (event['e'] - event['s'])
                    length = ((td.days * 1440) + (td.seconds / 60))
                    try:
                        new_start, new_end = get_time_from_str(
                                val.strip(), length, allday=self.all_day)
                    except ValueError as exc:
                        cli.print_err_msg(str(exc))
                        sys.exit(1)

                    event = self._set_event_start_end(
                                new_start, new_end, event)

            elif val.lower() == 'g':
                cli.print_msg(colors.CLR_MAG(), "Length (mins): ")
                val = input()
                if val.strip():
                    try:
                        new_start, new_end = get_time_from_str(
                            event['start']['dateTime'], val.strip(),
                            allday=self.all_day)
                    except ValueError as exc:
                        cli.print_err_msg(str(exc))
                        sys.exit(1)

                    event = self._set_event_start_end(
                                new_start, new_end, event)

            elif val.lower() == 'r':
                rem = []
                while 1:
                    cli.print_msg(colors.CLR_MAG(),
                                  "Enter a valid reminder or '.' to end: ")
                    r = input()
                    if r == '.':
                        break
                    rem.append(r)

                if rem or not self.defaultReminders:
                    event['reminders'] = {'useDefault': False,
                                          'overrides': []}
                    for r in rem:
                        n, m = parse_reminder(r)
                        event['reminders']['overrides'].append({'minutes': n,
                                                                'method': m})
                else:
                    event['reminders'] = {'useDefault': True,
                                          'overrides': []}

            elif val.lower() == 'd':
                cli.print_msg(colors.CLR_MAG(), "Description: ")
                val = input()
                if val.strip():
                    event['description'] = val.strip()

            else:
                cli.print_err_msg('Error: invalid input\n')
                sys.stdout.write('\n')
                sys.exit(1)

            self._print_event(event, event['s'].strftime('\n%Y-%m-%d'))

    def _iterate_events(self, startDateTime, event_list,
                        yearDate=False, work=None):

        if len(event_list) == 0:
            cli.print_msg(colors.CLR_YLW(), "\nNo Events Found...\n")
            return

        # 10 chars for day and length must match 'indent' in _print_event
        dayFormat = '\n%Y-%m-%d' if yearDate else '\n%a %b %d'
        day = ''

        for event in event_list:

            if self.ignore_started and (event['s'] < self.now):
                continue
            if self.ignoreDeclined:
                if 'attendees' in event:
                    attendee = [a for a in event['attendees']
                                if a['email'] == event['gcalcli_cal']['id']][0]
                    if attendee and attendee['responseStatus'] == 'declined':
                        continue

            tmpDayStr = event['s'].strftime(dayFormat)
            prefix = None
            if yearDate or tmpDayStr != day:
                day = prefix = tmpDayStr

            self._print_event(event, prefix)

            if work:
                work(event)

    def _GetAllEvents(self, cal, events, end):

        event_list = []

        while 1:
            if 'items' not in events:
                break

            for event in events['items']:

                event['gcalcli_cal'] = cal

                if 'status' in event and event['status'] == 'cancelled':
                    continue

                if 'dateTime' in event['start']:
                    event['s'] = parse(event['start']['dateTime'])
                else:
                    # all date events
                    event['s'] = parse(event['start']['date'])

                event['s'] = self._LocalizeDateTime(event['s'])

                if 'dateTime' in event['end']:
                    event['e'] = parse(event['end']['dateTime'])
                else:
                    # all date events
                    event['e'] = parse(event['end']['date'])

                event['e'] = self._LocalizeDateTime(event['e'])

                # For all-day events, Google seems to assume that the event
                # time is based in the UTC instead of the local timezone.  Here
                # we filter out those events start beyond a specified end time.
                if end and (event['s'] >= end):
                    continue

                # http://en.wikipedia.org/wiki/Year_2038_problem
                # Catch the year 2038 problem here as the python dateutil
                # module can choke throwing a ValueError exception. If either
                # the start or end time for an event has a year '>= 2038' dump
                # it.
                if event['s'].year >= 2038 or event['e'].year >= 2038:
                    continue

                event_list.append(event)

            pageToken = events.get('nextPageToken')
            if pageToken:
                events = self._retry_with_backoff(
                    self._cal_service().events().
                    list(calendarId=cal['id'], pageToken=pageToken))
            else:
                break

        return event_list

    def _search_for_cal_events(self, start, end, searchText):

        event_list = []
        for cal in self.cals:
            work = self._cal_service().events().\
                list(calendarId=cal['id'],
                     timeMin=start.isoformat() if start else None,
                     timeMax=end.isoformat() if end else None,
                     q=searchText if searchText else None,
                     singleEvents=True)
            events = self._retry_with_backoff(work)
            event_list.extend(self._GetAllEvents(cal, events, end))

        event_list.sort(key=lambda x: x['s'])

        return event_list

    def list_all_calendars(self):

        access_len = 0

        for cal in self.all_cals:
            length = len(cal['accessRole'])
            if length > access_len:
                access_len = length

        if access_len < len('Access'):
            access_len = len('Access')

        table_format = ' %0' + str(access_len) + 's  %s\n'

        cli.print_msg(colors.CLR_BRYLW(), table_format % ('Access', 'Title'))
        cli.print_msg(colors.CLR_BRYLW(), table_format % ('------', '-----'))

        for cal in self.all_cals:
            cli.print_msg(self._calendar_color(cal),
                          table_format % (cal['accessRole'], cal['summary']))

    def text_query(self, searchText='', start_text='', end_text=''):
        # the empty string would get *ALL* events...
        if searchText == '':
            return

        # This is really just an optimization to the gcalendar api
        # why ask for a bunch of events we are going to filter out
        # anyway?
        # TODO: Look at moving this into the _search_for_cal_events
        #       Don't forget to clean up agenda_query too!

        if start_text == '':
            start = self.now if self.ignore_started else None
        else:
            try:
                start = self.date_parser.from_string(start_text)
            except Exception:
                cli.print_err_msg('Error: failed to parse start time\n')
                return

        if end_text == '':
            end = None
        else:
            try:
                end = self.date_parser.from_string(end_text)
            except Exception:
                cli.print_err_msg('Error: failed to parse end time\n')
                return

        event_list = self._search_for_cal_events(start, end, searchText)

        if self.tsv:
            self._tsv(self.now, event_list)
        else:
            self._iterate_events(self.now, event_list, yearDate=True)

    def agenda_query(self, start_text='', end_text=''):

        if start_text == '':
            # convert now to midnight this morning and use for default
            start = self.now.replace(hour=0,
                                     minute=0,
                                     second=0,
                                     microsecond=0)
        else:
            try:
                start = self.date_parser.from_string(start_text)
            except Exception:
                cli.print_err_msg('Error: failed to parse start time\n')
                return

        # Again optimizing calls to the api.  If we've been told to
        # ignore started events, then it doesn't make ANY sense to
        # search for things that may be in the past
        if self.ignore_started and start < self.now:
            start = self.now

        if end_text == '':
            end = (start + timedelta(days=self.agendaLength))
        else:
            try:
                end = self.date_parser.from_string(end_text)
            except Exception:
                cli.print_err_msg('Error: failed to parse end time\n')
                return

        event_list = self._search_for_cal_events(start, end, None)

        if self.tsv:
            self._tsv(start, event_list)
        else:
            self._iterate_events(start, event_list, yearDate=False)

    def cal_query(self, cmd, start_text='', count=1):

        if start_text == '':
            # convert now to midnight this morning and use for default
            start = self.now.replace(hour=0,
                                     minute=0,
                                     second=0,
                                     microsecond=0)
        else:
            try:
                start = self.date_parser.from_string(start_text)
                start = start.replace(hour=0, minute=0, second=0,
                                      microsecond=0)
            except Exception:
                cli.print_err_msg('Error: failed to parse start time\n')
                return

        # convert start date to the beginning of the week or month
        if cmd == 'calw':
            dayNum = int(start.strftime("%w"))
            if self.calMonday:
                dayNum -= 1
                if dayNum < 0:
                    dayNum = 6
            start = (start - timedelta(days=dayNum))
            end = (start + timedelta(days=(count * 7)))
        else:  # cmd == 'calm':
            start = (start - timedelta(days=(start.day - 1)))
            endMonth = (start.month + 1)
            endYear = start.year
            if endMonth == 13:
                endMonth = 1
                endYear += 1
            end = start.replace(month=endMonth, year=endYear)
            daysInMonth = (end - start).days
            offsetDays = int(start.strftime('%w'))
            if self.calMonday:
                offsetDays -= 1
                if offsetDays < 0:
                    offsetDays = 6
            totalDays = (daysInMonth + offsetDays)
            count = (totalDays // 7)
            if totalDays % 7:
                count += 1

        event_list = self._search_for_cal_events(start, end, None)

        self._graph_events(cmd, start, count, event_list)

    def quick_add_event(self, eventText, reminder=None):

        if eventText == '':
            return

        if len(self.cals) > 1:
            cli.print_err_msg("You must only specify a single calendar\n")
            return

        if len(self.cals) < 1:
            cli.print_err_msg(
                """Calendar not specified or not found.
If "gcalcli list" doesn't find the calendar you're trying to use,
your cache file might be stale and you might need to remove it and try again.
""")
            return

        newEvent = self._retry_with_backoff(
            self._cal_service().events().quickAdd(
                calendarId=self.cals[0]['id'], text=eventText))

        if reminder or not self.defaultReminders:
            rem = {}
            rem['reminders'] = {'useDefault': False,
                                'overrides': []}
            for r in reminder:
                n, m = parse_reminder(r)
                rem['reminders']['overrides'].append({'minutes': n,
                                                      'method': m})

            newEvent = self._retry_with_backoff(
                self._cal_service().events().
                patch(calendarId=self.cals[0]['id'],
                      eventId=newEvent['id'],
                      body=rem))

        if self.detail_url:
            hLink = self._ShortenURL(newEvent['htmlLink'])
            cli.print_msg(colors.CLR_GRN(), 'New event added: %s\n' % hLink)

    def add_event(self, eTitle, eWhere, eStart, eEnd, eDescr, eWho, reminder):

        if len(self.cals) != 1:
            cli.print_err_msg("Must specify a single calendar\n")
            return

        event = {}
        event['summary'] = eTitle

        if self.all_day:
            event['start'] = {'date': eStart}
            event['end'] = {'date': eEnd}

        else:
            event['start'] = {'dateTime': eStart,
                              'timeZone': self.cals[0]['timeZone']}
            event['end'] = {'dateTime': eEnd,
                            'timeZone': self.cals[0]['timeZone']}

        if eWhere:
            event['location'] = eWhere
        if eDescr:
            event['description'] = eDescr

        event['attendees'] = map(lambda w: {'email': w}, eWho)

        if reminder or not self.defaultReminders:
            event['reminders'] = {'useDefault': False,
                                  'overrides': []}
            for r in reminder:
                n, m = parse_reminder(r)
                event['reminders']['overrides'].append({'minutes': n,
                                                        'method': m})

        newEvent = self._retry_with_backoff(
            self._cal_service().events().
            insert(calendarId=self.cals[0]['id'], body=event))

        if self.detail_url:
            hLink = self._ShortenURL(newEvent['htmlLink'])
            cli.print_msg(colors.CLR_GRN(), 'New event added: %s\n' % hLink)

    def delete_events(self, searchText='', expert=False, start=None, end=None):

        # the empty string would get *ALL* events...
        if searchText == '':
            return

        event_list = self._search_for_cal_events(start, end, searchText)

        self.iamaExpert = expert
        self._iterate_events(self.now, event_list,
                             yearDate=True, work=self._delete_event)

    def EditEvents(self, searchText=''):

        # the empty string would get *ALL* events...
        if searchText == '':
            return

        event_list = self._search_for_cal_events(None, None, searchText)

        self._iterate_events(self.now, event_list,
                             yearDate=True, work=self._edit_event)

    def Remind(self, minutes=10, command=None, use_reminders=False):
        """Check for events between now and now+minutes.
           If use_reminders is True, then only remind if
           now >= event['start'] - reminder"""

        if command is None:
            command = self.command

        # perform a date query for now + minutes + slip
        start = self.now
        end = (start + timedelta(minutes=(minutes + 5)))

        event_list = self._search_for_cal_events(start, end, None)

        message = ''

        for event in event_list:

            # skip this event if it already started
            # XXX maybe add a 2+ minute grace period here...
            if event['s'] < self.now:
                continue

            # not sure if 'reminders' always in event
            if use_reminders and 'reminders' in event \
                    and 'overrides' in event['reminders']:
                if all(event['s'] - timedelta(minutes=r['minutes']) > self.now
                   for r in event['reminders']['overrides']):
                    continue  # don't remind if all reminders haven't arrived

            if self.military:
                tmp_time_str = event['s'].strftime('%H:%M')
            else:
                tmp_time_str = \
                    event['s'].strftime('%I:%M').lstrip('0') + \
                    event['s'].strftime('%p').lower()

            message += '%s  %s\n' % \
                       (tmp_time_str, self._ValidTitle(event).strip())

        if message == '':
            return

        cmd = shlex.split(command)

        for i, a in zip(range(len(cmd)), cmd):
            if a == '%s':
                cmd[i] = message

        pid = os.fork()
        if not pid:
            os.execvp(cmd[0], cmd)

    def ImportICS(self, verbose=False, dump=False, reminder=None,
                  icsFile=None):

        def CreateEventFromVOBJ(ve):

            event = {}

            if verbose:
                print("+----------------+")
                print("| Calendar Event |")
                print("+----------------+")

            if hasattr(ve, 'summary'):
                cli.debug_print("SUMMARY: %s\n" % ve.summary.value)
                if verbose:
                    print("Event........{}".format(ve.summary.value))
                event['summary'] = ve.summary.value

            if hasattr(ve, 'location'):
                cli.debug_print("LOCATION: %s\n" % ve.location.value)
                if verbose:
                    print("Location.....{}".format(ve.location.value))
                event['location'] = ve.location.value

            if not hasattr(ve, 'dtstart') or not hasattr(ve, 'dtend'):
                cli.print_err_msg(
                        "Error: event does not have a dtstart and dtend!\n")
                return None

            if ve.dtstart.value:
                cli.debug_print("DTSTART: %s\n" % ve.dtstart.value.isoformat())
            if ve.dtend.value:
                cli.debug_print("DTEND: %s\n" % ve.dtend.value.isoformat())
            if verbose:
                if ve.dtstart.value:
                    print("Start........{}".format(
                        ve.dtstart.value.isoformat()))
                if ve.dtend.value:
                    print("End..........{}".format(
                        ve.dtend.value.isoformat()))
                if ve.dtstart.value:
                    print("Local Start..{}".format(
                        self._LocalizeDateTime(ve.dtstart.value)))
                if ve.dtend.value:
                    print("Local End....{}".format(
                        self._LocalizeDateTime(ve.dtend.value)))

            if hasattr(ve, 'rrule'):

                cli.debug_print("RRULE: %s\n" % ve.rrule.value)
                if verbose:
                    print("Recurrence...%s" % ve.rrule.value)

                event['recurrence'] = ["RRULE:" + ve.rrule.value]

            if hasattr(ve, 'dtstart') and ve.dtstart.value:
                # XXX
                # Timezone madness! Note that we're using the timezone for the
                # calendar being added to. This is OK if the event is in the
                # same timezone. This needs to be changed to use the timezone
                # from the DTSTART and DTEND values. Problem is, for example,
                # the TZID might be "Pacific Standard Time" and Google expects
                # a timezone string like "America/Los_Angeles". Need to find
                # a way in python to convert to the more specific timezone
                # string.
                # XXX
                # print ve.dtstart.params['X-VOBJ-ORIGINAL-TZID'][0]
                # print self.cals[0]['timeZone']
                # print dir(ve.dtstart.value.tzinfo)
                # print vars(ve.dtstart.value.tzinfo)

                start = ve.dtstart.value.isoformat()
                if isinstance(ve.dtstart.value, datetime):
                    event['start'] = {'dateTime': start,
                                      'timeZone': self.cals[0]['timeZone']}
                else:
                    event['start'] = {'date': start}

                if reminder or not self.defaultReminders:
                    event['reminders'] = {'useDefault': False,
                                          'overrides': []}
                    for r in reminder:
                        n, m = parse_reminder(r)
                        event['reminders']['overrides'].append({'minutes': n,
                                                                'method': m})

                # Can only have an end if we have a start, but not the other
                # way around apparently...  If there is no end, use the start
                if hasattr(ve, 'dtend') and ve.dtend.value:
                    end = ve.dtend.value.isoformat()
                    if isinstance(ve.dtend.value, datetime):
                        event['end'] = {'dateTime': end,
                                        'timeZone': self.cals[0]['timeZone']}
                    else:
                        event['end'] = {'date': end}

                else:
                    event['end'] = event['start']

            if hasattr(ve, 'description') and ve.description.value.strip():
                descr = ve.description.value.strip()
                cli.debug_print("DESCRIPTION: %s\n" % descr)
                if verbose:
                    print("Description:\n%s" % descr)
                event['description'] = descr

            if hasattr(ve, 'organizer'):
                cli.debug_print("ORGANIZER: %s\n" % ve.organizer.value)

                if ve.organizer.value.startswith("MAILTO:"):
                    email = ve.organizer.value[7:]
                else:
                    email = ve.organizer.value
                if verbose:
                    print("organizer:\n %s" % email)
                event['organizer'] = {'displayName': ve.organizer.name,
                                      'email': email}

            if hasattr(ve, 'attendee_list'):
                cli.debug_print("ATTENDEE_LIST : %s\n" % ve.attendee_list)
                if verbose:
                    print("attendees:")
                event['attendees'] = []
                for attendee in ve.attendee_list:
                    if attendee.value.upper().startswith("MAILTO:"):
                        email = attendee.value[7:]
                    else:
                        email = attendee.value
                    if verbose:
                        print(" %s" % email)

                    event['attendees'].append({'displayName': attendee.name,
                                               'email': email})

            return event

        try:
            import vobject
        except ImportError:
            cli.print_err_msg('Python vobject module not installed!\n')
            sys.exit(1)

        if dump:
            verbose = True

        if not dump and len(self.cals) != 1:
            cli.print_err_msg("Must specify a single calendar\n")
            return

        f = sys.stdin

        if icsFile:
            try:
                f = open(icsFile)
            except Exception as e:
                cli.print_err_msg("Error: " + str(e) + "!\n")
                sys.exit(1)

        while True:

            try:
                v = vobject.readComponents(f).next()
            except StopIteration:
                break

            for ve in v.vevent_list:

                event = CreateEventFromVOBJ(ve)

                if not event:
                    continue

                if dump:
                    continue

                if not verbose:
                    newEvent = self._retry_with_backoff(
                        self._cal_service().events().
                        insert(calendarId=self.cals[0]['id'],
                               body=event))
                    hLink = self._ShortenURL(newEvent['htmlLink'])
                    cli.print_msg(
                            colors.CLR_GRN(), 'New event added: %s\n' % hLink)
                    continue

                cli.print_msg(colors.CLR_MAG(), "\n[S]kip [i]mport [q]uit: ")
                val = input()
                if not val or val.lower() == 's':
                    continue
                if val.lower() == 'i':
                    newEvent = self._retry_with_backoff(
                        self._cal_service().events().
                        insert(calendarId=self.cals[0]['id'],
                               body=event))
                    hLink = self._ShortenURL(newEvent['htmlLink'])
                    cli.print_msg(
                            colors.CLR_GRN(), 'New event added: %s\n' % hLink)
                elif val.lower() == 'q':
                    sys.exit(0)
                else:
                    cli.print_err_msg('Error: invalid input\n')
                    sys.exit(1)


def parse_reminder(rem):
    matchObj = re.match(r'^(\d+)([wdhm]?)(?:\s+(popup|email|sms))?$', rem)
    if not matchObj:
        cli.print_err_msg('Invalid reminder: ' + rem + '\n')
        sys.exit(1)
    n = int(matchObj.group(1))
    t = matchObj.group(2)
    m = matchObj.group(3)
    if t == 'w':
        n = n * 7 * 24 * 60
    elif t == 'd':
        n = n * 24 * 60
    elif t == 'h':
        n = n * 60

    if not m:
        m = 'popup'

    return n, m
