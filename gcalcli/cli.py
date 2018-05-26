#!/usr/bin/env python3
import locale
import os
import signal
import sys
from gcalcli import (__API_CLIENT_ID__, __API_CLIENT_SECRET__, __program__,
                     __version__, __author__, colors)

from gcalcli import gcal
from gcalcli.utils import get_time_from_str

# Required 3rd party libraries
try:
    import gflags
except ImportError as e:
    print("ERROR: Missing module - {}".format(e.args[0]))
    sys.exit(1)

# ** The MIT License **
#
# Copyright (c) 2007 Eric Davis (aka Insanum)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Dude... just buy us a beer. :-)
#

# XXX Todo/Cleanup XXX
# threading is currently broken when getting event list
# if threading works then move pageToken processing from GetAllEvents to thread
# support different types of reminders plus multiple ones (popup, sms, email)
# add caching, should be easy (dump all calendar JSON data to file)
# add support for multiline description input in the 'add' and 'edit' commands
# maybe add support for freebusy ?

#############################################################################
#                                                                           #
#                                      (           (     (                  #
#               (         (     (      )\ )   (    )\ )  )\ )               #
#               )\ )      )\    )\    (()/(   )\  (()/( (()/(               #
#              (()/(    (((_)((((_)(   /(_))(((_)  /(_)) /(_))              #
#               /(_))_  )\___ )\ _ )\ (_))  )\___ (_))  (_))                #
#              (_)) __|((/ __|(_)_\(_)| |  ((/ __|| |   |_ _|               #
#                | (_ | | (__  / _ \  | |__ | (__ | |__  | |                #
#                 \___|  \___|/_/ \_\ |____| \___||____||___|               #
#                                                                           #
# Author: Eric Davis <http://www.insanum.com>                               #
#         Brian Hartvigsen <http://github.com/tresni>                       #
# Home: https://github.com/insanum/gcalcli                                  #
#                                                                           #
# Requirements:                                                             #
#  - Python 2                                                               #
#        http://www.python.org                                              #
#  - Google APIs Client Library for Python 2                                #
#        https://developers.google.com/api-client-library/python            #
#  - dateutil Python 2 module                                               #
#        http://www.labix.org/python-dateutil                               #
#                                                                           #
# Optional:                                                                 #
#  - vobject Python module (needed for importing ics/vcal files)            #
#        http://vobject.skyhouseconsulting.com                              #
#  - parsedatetime Python module (needed for fuzzy date parsing)            #
#        https://github.com/bear/parsedatetime                              #
#                                                                           #
# Everything you need to know (Google API Calendar v3): http://goo.gl/HfTGQ #
#                                                                           #
#############################################################################


def version():
    print(__program__,  __version__,  ' (', __author__,  ')')


def usage(expanded=False):
    print(__doc__ % sys.argv[0])
    if expanded:
        print(expanded())


def get_cal_colors(cal_names):
    cal_colors = {}
    for cal_name in cal_names:
        cal_name_parts = cal_name.split("#")
        cal_name_simple = cal_name_parts[0]
        cal_color = cal_colors.get(cal_name_simple)
        if len(cal_name_parts) > 0:
            cal_color_raw = cal_name_parts[-1]
            cal_color_obj = get_color(cal_color_raw)
            if cal_color_obj is not None:
                cal_color = cal_color_obj
        cal_colors[cal_name_simple] = cal_color
    return cal_colors


def get_color(value):
    color_names = {'default': colors.CLR_NRM(),
                   'black': colors.CLR_BLK(),
                   'brightblack': colors.CLR_BRBLK(),
                   'red': colors.CLR_RED(),
                   'brightred': colors.CLR_BRRED(),
                   'green': colors.CLR_GRN(),
                   'brightgreen': colors.CLR_BRGRN(),
                   'yellow': colors.CLR_YLW(),
                   'brightyellow': colors.CLR_BRYLW(),
                   'blue': colors.CLR_BLU(),
                   'brightblue': colors.CLR_BRBLU(),
                   'magenta': colors.CLR_MAG(),
                   'brightmagenta': colors.CLR_BRMAG(),
                   'cyan': colors.CLR_CYN(),
                   'brightcyan': colors.CLR_BRCYN(),
                   'white': colors.CLR_WHT(),
                   'brightwhite': colors.CLR_BRWHT(),
                   None: colors.CLR_NRM()}

    if value in color_names:
        return color_names[value]
    else:
        return None


def debug_print(msg):
    print_msg(colors.CLR_YLW(), msg)


def print_err_msg(msg):
    print_msg(colors.CLR_BRRED(), msg)


def print_msg(color, msg):
    if colors.CLR.use_color:
        msg = str(color) + msg + str(colors.CLR_NRM())
    print(msg, end='')


def parse_args(argv=sys.argv):
    flags = gflags.FLAGS
    flags.UseGnuGetOpt()  # allow mixing of commands and options
    gflags.DEFINE_bool("help", None, "Show this help")
    gflags.DEFINE_bool("helpshort", None, "Show command help only")
    gflags.DEFINE_bool("version", False, "Show the version and exit")
    gflags.DEFINE_string("client_id", __API_CLIENT_ID__, "API client_id")
    gflags.DEFINE_string(
            "client_secret", __API_CLIENT_SECRET__, "API client_secret")
    gflags.DEFINE_string(
            "config_folder", None,
            "Optional directory to load/store all configuration "
            "information")
    gflags.DEFINE_bool(
            "includeRc", False,
            "Whether to include ~/.gcalclirc when using config_folder")
    gflags.DEFINE_multistring("calendar", [], "Which calendars to use")
    gflags.DEFINE_multistring(
            "default_calendar", [],
            "Optional default calendar to use if no --calendar "
            "options are given")
    gflags.DEFINE_bool("military", False, "Use 24 hour display")
    # Single --detail that allows you to specify what parts you want
    gflags.DEFINE_multistring(
            "details", [], "Which parts to display, can be: "
            "'all', 'calendar', 'location', 'length', "
            "'reminders', 'description', 'longurl', 'shorturl', "
            "'url', 'attendees', 'email'")
    # old style flags for backwards compatibility
    gflags.DEFINE_bool("detail_all", False, "Display all details")
    gflags.DEFINE_bool("detail_calendar", False, "Display calendar name")
    gflags.DEFINE_bool("detail_location", False, "Display event location")
    gflags.DEFINE_bool(
            "detail_attendees", False, "Display event attendees")
    gflags.DEFINE_bool(
            "detail_attachments", False, "Display event attachments")
    gflags.DEFINE_bool("detail_length", False, "Display length of event")
    gflags.DEFINE_bool("detail_reminders", False, "Display reminders")
    gflags.DEFINE_bool("detail_description", False, "Display description")
    gflags.DEFINE_bool("detail_email", False, "Display creator email")
    gflags.DEFINE_integer(
            "detail_description_width", 80, "Set description width")
    gflags.DEFINE_enum("detail_url", None, ["long", "short"], "Set URL output")
    gflags.DEFINE_bool("tsv", False, "Use Tab Separated Value output")
    gflags.DEFINE_bool("started", True, "Show events that have started")
    gflags.DEFINE_bool("declined", True, "Show events that have been declined")
    gflags.DEFINE_integer("width", 10, "Set output width", short_name="w")
    gflags.DEFINE_bool("monday", False, "Start the week on Monday")
    gflags.DEFINE_bool("color", True, "Enable/Disable all color output")
    gflags.DEFINE_bool("lineart", True, "Enable/Disable line art")
    gflags.DEFINE_bool("conky", False, "Use Conky color codes")
    gflags.DEFINE_string("color_owner", "cyan", "Color for owned calendars")
    gflags.DEFINE_string(
            "color_writer", "green", "Color for writable calendars")
    gflags.DEFINE_string(
            "color_reader", "magenta", "Color for read-only calendars")
    gflags.DEFINE_string(
            "color_freebusy", "default", "Color for free/busy calendars")
    gflags.DEFINE_string("color_date", "yellow", "Color for the date")
    gflags.DEFINE_string(
            "color_now_marker", "brightred", "Color for the now marker")
    gflags.DEFINE_string("color_border", "white", "Color of line borders")
    gflags.DEFINE_string("locale", None, "System locale")
    gflags.DEFINE_multistring(
            "reminder", [],
            "Reminders in the form 'TIME METH' or 'TIME'.  TIME "
            "is a number which may be followed by an optional "
            "'w', 'd', 'h', or 'm' (meaning weeks, days, hours, "
            "minutes) and default to minutes.  METH is a string "
            "'popup', 'email', or 'sms' and defaults to popup.")
    gflags.DEFINE_string("title", None, "Event title")
    gflags.DEFINE_multistring("who", [], "Event attendees")
    gflags.DEFINE_string("where", None, "Event location")
    gflags.DEFINE_string("when", None, "Event time")
    gflags.DEFINE_integer(
            "duration", None,
            "Event duration in minutes or days if --allday is given.")
    gflags.DEFINE_string("description", None, "Event description")
    gflags.DEFINE_bool(
            "allday", False,
            "If --allday is given, the event will be an all-day event "
            "(possibly multi-day if --duration is greater than 1). The "
            "time part of the --when will be ignored.")
    gflags.DEFINE_bool(
            "prompt", True, "Prompt for missing data when adding events")
    gflags.DEFINE_bool(
            "default_reminders", True,
            "If no --reminder is given, use the defaults.  If this is "
            "false, do not create any reminders.")
    gflags.DEFINE_bool("iamaexpert", False, "Probably not")
    gflags.DEFINE_bool("refresh", False, "Delete and refresh cached data")
    gflags.DEFINE_bool("cache", True, "Execute command without using cache")
    gflags.DEFINE_bool(
            "verbose", False, "Be verbose on imports", short_name="v")
    gflags.DEFINE_bool(
            "dump", False, "Print events and don't import", short_name="d")
    gflags.DEFINE_bool(
            "use_reminders", False,
            "Honour the remind time when running remind command")
    gflags.RegisterValidator(
            "details",
            lambda value: all(x in ["all", "calendar", "location", "length",
                                    "reminders", "description", "longurl",
                                    "shorturl", "url", "attendees",
                                    "attachments", "email"] for x in value))
    gflags.RegisterValidator(
            "reminder",
            lambda value: all(gcal.parse_reminder(x) for x in value))
    gflags.RegisterValidator(
            "color_owner", lambda value: get_color(value) is not None)
    gflags.RegisterValidator(
            "color_writer", lambda value: get_color(value) is not None)
    gflags.RegisterValidator(
            "color_reader", lambda value: get_color(value) is not None)
    gflags.RegisterValidator(
            "color_freebusy", lambda value: get_color(value) is not None)
    gflags.RegisterValidator(
            "color_date", lambda value: get_color(value) is not None)
    gflags.RegisterValidator(
            "color_now_marker", lambda value: get_color(value) is not None)
    gflags.RegisterValidator(
            "color_border", lambda value: get_color(value) is not None)
    gflags.ADOPT_module_key_flags(gflags)

    try:
        if os.path.exists(os.path.expanduser('~/.gcalclirc')):
            # We want .gcalclirc to be sourced before any other --flagfile
            # params since we may be told to use a specific config folder, we
            # need to store generated argv in temp variable
            tmpArgv = [argv[0], "--flagfile=~/.gcalclirc"] + argv[1:]
        else:
            tmpArgv = argv
        args = flags(tmpArgv)
    except gflags.FlagsError as e:
        print_err_msg(str(e))
        usage(flags.MainModuleHelp)
        sys.exit(1)

    if flags.config_folder:
        if not os.path.exists(os.path.expanduser(flags.config_folder)):
            os.makedirs(os.path.expanduser(flags.config_folder))
        if os.path.exists(os.path.expanduser("%s/gcalclirc" %
                                             flags.config_folder)):
            if not flags.includeRc:
                tmpArgv = argv + ["--flagfile=%s/gcalclirc" %
                                  flags.config_folder, ]
            else:
                tmpArgv += ["--flagfile=%s/gcalclirc" % flags.config_folder, ]

        flags.Reset()
        args = flags(tmpArgv)

    return args, flags


def main():
    args, flags = parse_args()

    if flags.version:
        version()
        sys.exit(0)

    if flags.help:
        usage(True)
        sys.exit(0)

    if flags.helpshort:
        usage()
        sys.exit(0)

    if not flags.color:
        colors.CLR.use_color = False

    if not flags.lineart:
        gcal.ART.useArt = False

    if flags.conky:
        colors.SetConkyColors()

    if flags.locale:
        try:
            locale.setlocale(locale.LC_ALL, flags.locale)
        except Exception as e:
            print_err_msg("Error: " + str(e) + "!\n"
                          "Check supported locales of your system.\n")
            sys.exit(1)

    # pop executable off the stack
    args = args[1:]
    if len(args) == 0:
        print_err_msg('Error: no command\n')
        sys.exit(1)

    # No sense instaniating gcalcli for nothing
    if not args[0] in ['list', 'search', 'agenda', 'calw', 'calm', 'quick',
                       'add', 'delete', 'edit', 'remind', 'import', 'help']:
        print_err_msg('Error: %s is an invalid command' % args[0])
        sys.exit(1)

    # all other commands require gcalcli be brought up
    if args[0] == 'help':
        usage()
        sys.exit(0)

    if len(flags.calendar) == 0:
        flags.calendar = flags.default_calendar

    cal_names = []
    cal_name_colors = []
    cal_colors = get_cal_colors(flags.calendar)
    cal_names_filtered = []
    for cal_name in flags.calendar:
        cal_name_simple = cal_name.split("#")[0]
        cal_names_filtered.append(cal_name_simple)
        cal_name_colors.append(cal_colors[cal_name_simple])
    cal_names = cal_names_filtered

    if 'all' in flags.details or flags.detail_all:
        if not flags['detail_calendar'].present:
            flags['detail_calendar'].value = True
        if not flags['detail_location'].present:
            flags['detail_location'].value = True
        if not flags['detail_length'].present:
            flags['detail_length'].value = True
        if not flags['detail_reminders'].present:
            flags['detail_reminders'].value = True
        if not flags['detail_description'].present:
            flags['detail_description'].value = True
        if not flags['detail_url'].present:
            flags['detail_url'].value = "long"
        if not flags['detail_attendees'].present:
            flags['detail_attendees'].value = True
        if not flags['detail_attachments'].present:
            flags['detail_attachments'].value = True
        if not flags['detail_email'].present:
            flags['detail_email'].value = True
    else:
        if 'calendar' in flags.details:
            flags['detail_calendar'].value = True
        if 'location' in flags.details:
            flags['detail_location'].value = True
        if 'attendees' in flags.details:
            flags['detail_attendees'].value = True
        if 'attachments' in flags.details:
            flags['detail_attachments'].value = True
        if 'length' in flags.details:
            flags['detail_length'].value = True
        if 'reminders' in flags.details:
            flags['detail_reminders'].value = True
        if 'description' in flags.details:
            flags['detail_description'].value = True
        if 'longurl' in flags.details or 'url' in flags.details:
            flags['detail_url'].value = 'long'
        elif 'shorturl' in flags.details:
            flags['detail_url'].value = 'short'
        if 'attendees' in flags.details:
            flags['detail_attendees'].value = True
        if 'email' in flags.details:
            flags['detail_email'].value = True

    gci = gcal.GoogleCalendarInterface(
           cal_names=cal_names,
           cal_name_colors=cal_name_colors,
           military=flags.military,
           detail_calendar=flags.detail_calendar,
           detail_location=flags.detail_location,
           detail_attendees=flags.detail_attendees,
           detail_attachments=flags.detail_attachments,
           detail_length=flags.detail_length,
           detail_reminder=flags.detail_reminders,
           detail_descr=flags.detail_description,
           detail_descr_width=flags.detail_description_width,
           detail_url=flags.detail_url,
           detail_email=flags.detail_email,
           ignore_started=not flags.started,
           ignoreDeclined=not flags.declined,
           calWidth=flags.width,
           calMonday=flags.monday,
           calOwnerColor=get_color(flags.color_owner),
           calWriterColor=get_color(flags.color_writer),
           calReaderColor=get_color(flags.color_reader),
           calFreeBusyColor=get_color(flags.color_freebusy),
           date_color=get_color(flags.color_date),
           nowMarkerColor=get_color(flags.color_now_marker),
           border_color=get_color(flags.color_border),
           tsv=flags.tsv,
           refresh_cache=flags.refresh,
           use_cache=flags.cache,
           config_folder=flags.config_folder,
           client_id=flags.client_id,
           client_secret=flags.client_secret,
           defaultReminders=flags.default_reminders,
           all_day=flags.allday)

    if args[0] == 'list':
        gci.list_all_calendars()

    elif args[0] == 'search':
        if len(args) == 4:  # start and end
            gci.text_query(args[1], start_text=args[2], end_text=args[3])
        elif len(args) == 3:  # start
            gci.text_query(args[1], start_text=args[2])
        elif len(args) == 2:  # defaults
            gci.text_query(args[1])
        else:
            print_err_msg('Error: invalid search string\n')
            sys.exit(1)

        if not flags.tsv:
            sys.stdout.write('\n')

    elif args[0] == 'agenda':

        if len(args) == 3:  # start and end
            gci.agenda_query(start_text=args[1], end_text=args[2])
        elif len(args) == 2:  # start
            gci.agenda_query(start_text=args[1])
        elif len(args) == 1:  # defaults
            gci.agenda_query()
        else:
            print_err_msg('Error: invalid agenda arguments\n')
            sys.exit(1)

        if not flags.tsv:
            sys.stdout.write('\n')

    elif args[0] == 'calw':
        if not flags.width:
            print_err_msg('Error: invalid width, don\'t be an idiot!\n')
            sys.exit(1)

        if len(args) >= 2:
            try:
                # Test to make sure args[1] is a number
                int(args[1])
            except Exception:
                print_err_msg('Error: invalid calw arguments\n')
                sys.exit(1)

        if len(args) == 3:  # weeks and start
            gci.cal_query(args[0], count=int(args[1]), start_text=args[2])
        elif len(args) == 2:  # weeks
            gci.cal_query(args[0], count=int(args[1]))
        elif len(args) == 1:  # defaults
            gci.cal_query(args[0])
        else:
            print_err_msg('Error: invalid calw arguments\n')
            sys.exit(1)

        sys.stdout.write('\n')

    elif args[0] == 'calm':
        if not flags.width:
            print_err_msg('Error: invalid width, don\'t be an idiot!\n')
            sys.exit(1)

        if len(args) == 2:  # start
            gci.cal_query(args[0], start_text=args[1])
        elif len(args) == 1:  # defaults
            gci.cal_query(args[0])
        else:
            print_err_msg('Error: invalid calm arguments\n')
            sys.exit(1)

        sys.stdout.write('\n')

    elif args[0] == 'quick':
        if len(args) != 2:
            print_err_msg('Error: invalid event text\n')
            sys.exit(1)

        gci.quick_add_event(args[1], reminder=flags.reminder)

    elif (args[0] == 'add'):
        if flags.prompt:
            if flags.title is None:
                print_msg(colors.CLR_MAG(), "Title: ")
                flags.title = input()
            if flags.where is None:
                print_msg(colors.CLR_MAG(), "Location: ")
                flags.where = input()
            if flags.when is None:
                print_msg(colors.CLR_MAG(), "When: ")
                flags.when = input()
            if flags.duration is None:
                if flags.allday:
                    print_msg(colors.CLR_MAG(), "Duration (days): ")
                else:
                    print_msg(colors.CLR_MAG(), "Duration (mins): ")
                flags.duration = input()
            if flags.description is None:
                print_msg(colors.CLR_MAG(), "Description: ")
                flags.description = input()
            if not flags.reminder:
                while 1:
                    print_msg(colors.CLR_MAG(),
                              "Enter a valid reminder or '.' to end: ")
                    r = input()
                    if r == '.':
                        break
                    n, m = gcal.parse_reminder(str(r))
                    flags.reminder.append(str(n) + ' ' + m)

        # calculate "when" time:
        try:
            e_start, e_end = get_time_from_str(
                    flags.when, flags.duration, flags.allday)
        except ValueError as exc:
            print_err_msg(str(exc))
            sys.exit(1)

        gci.add_event(flags.title, flags.where, e_start, e_end,
                      flags.description, flags.who,
                      flags.reminder)

    elif args[0] == 'delete':
        event_start = None
        event_end = None
        if len(args) < 2:
            print_err_msg('Error: invalid search string\n')
            sys.exit(1)
        elif len(args) == 4:  # search, start, end
            event_start = gci.date_parser.from_string(args[2])
            event_end = gci.date_parser.from_string(args[3])
        elif len(args) == 3:  # search, start (default end)
            event_start = gci.date_parser.from_string(args[2])

        gci.delete_events(args[1], flags.iamaexpert, event_start, event_end)

        sys.stdout.write('\n')

    elif args[0] == 'edit':
        if len(args) != 2:
            print_err_msg('Error: invalid search string\n')
            sys.exit(1)

        gci.EditEvents(args[1])

        sys.stdout.write('\n')

    elif args[0] == 'remind':
        if len(args) == 3:  # minutes and command
            gci.Remind(int(args[1]),
                       args[2], use_reminders=flags.use_reminders)
        elif len(args) == 2:  # minutes
            gci.Remind(int(args[1]), use_reminders=flags.use_reminders)
        elif len(args) == 1:  # defaults
            gci.Remind(use_reminders=flags.use_reminders)
        else:
            print_err_msg('Error: invalid remind arguments\n')
            sys.exit(1)

    elif args[0] == 'import':
        if len(args) == 1:  # stdin
            gci.ImportICS(flags.verbose, flags.dump, flags.reminder)
        elif len(args) == 2:  # ics file
            gci.ImportICS(flags.verbose, flags.dump, flags.reminder, args[1])
        else:
            print_err_msg('Error: invalid import arguments\n')
            sys.exit(1)


def SIGINT_handler(signum, frame):
    print_err_msg('Signal caught, bye!\n')
    sys.exit(1)


signal.signal(signal.SIGINT, SIGINT_handler)

if __name__ == '__main__':
    main()
