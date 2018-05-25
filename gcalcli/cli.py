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


FLAGS = gflags.FLAGS
# allow mixing of commands and options
FLAGS.UseGnuGetOpt()

gflags.DEFINE_bool("help", None, "Show this help")
gflags.DEFINE_bool("helpshort", None, "Show command help only")
gflags.DEFINE_bool("version", False, "Show the version and exit")

gflags.DEFINE_string("client_id", __API_CLIENT_ID__, "API client_id")
gflags.DEFINE_string("client_secret", __API_CLIENT_SECRET__,
                     "API client_secret")

gflags.DEFINE_string("config_folder", None,
                     "Optional directory to load/store all configuration "
                     "information")
gflags.DEFINE_bool("includeRc", False,
                   "Whether to include ~/.gcalclirc when using config_folder")
gflags.DEFINE_multistring("calendar", [], "Which calendars to use")
gflags.DEFINE_multistring("default_calendar", [],
                          "Optional default calendar to use if no --calendar "
                          "options are given")
gflags.DEFINE_bool("military", False, "Use 24 hour display")

# Single --detail that allows you to specify what parts you want
gflags.DEFINE_multistring("details", [], "Which parts to display, can be: "
                          "'all', 'calendar', 'location', 'length', "
                          "'reminders', 'description', 'longurl', 'shorturl', "
                          "'url', 'attendees', 'email'")
# old style flags for backwards compatibility
gflags.DEFINE_bool("detail_all", False, "Display all details")
gflags.DEFINE_bool("detail_calendar", False, "Display calendar name")
gflags.DEFINE_bool("detail_location", False, "Display event location")
gflags.DEFINE_bool("detail_attendees", False, "Display event attendees")
gflags.DEFINE_bool("detail_attachments", False, "Display event attachments")
gflags.DEFINE_bool("detail_length", False, "Display length of event")
gflags.DEFINE_bool("detail_reminders", False, "Display reminders")
gflags.DEFINE_bool("detail_description", False, "Display description")
gflags.DEFINE_bool("detail_email", False, "Display creator email")
gflags.DEFINE_integer("detail_description_width", 80, "Set description width")
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
gflags.DEFINE_string("color_writer", "green", "Color for writable calendars")
gflags.DEFINE_string("color_reader", "magenta",
                     "Color for read-only calendars")
gflags.DEFINE_string("color_freebusy", "default",
                     "Color for free/busy calendars")
gflags.DEFINE_string("color_date", "yellow", "Color for the date")
gflags.DEFINE_string("color_now_marker", "brightred",
                     "Color for the now marker")
gflags.DEFINE_string("color_border", "white", "Color of line borders")

gflags.DEFINE_string("locale", None, "System locale")

gflags.DEFINE_multistring("reminder", [],
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
gflags.DEFINE_bool("allday", False,
                   "If --allday is given, the event will be an all-day event "
                   "(possibly multi-day if --duration is greater than 1). The "
                   "time part of the --when will be ignored.")
gflags.DEFINE_bool("prompt", True,
                   "Prompt for missing data when adding events")
gflags.DEFINE_bool("default_reminders", True,
                   "If no --reminder is given, use the defaults.  If this is "
                   "false, do not create any reminders.")

gflags.DEFINE_bool("iamaexpert", False, "Probably not")
gflags.DEFINE_bool("refresh", False, "Delete and refresh cached data")
gflags.DEFINE_bool("cache", True, "Execute command without using cache")

gflags.DEFINE_bool("verbose", False, "Be verbose on imports",
                   short_name="v")
gflags.DEFINE_bool("dump", False, "Print events and don't import",
                   short_name="d")

gflags.DEFINE_bool("use_reminders", False,
                   "Honour the remind time when running remind command")

gflags.RegisterValidator("details",
                         lambda value: all(x in [
                             "all", "calendar", "location", "length",
                             "reminders", "description", "longurl",
                             "shorturl", "url", "attendees", "attachments",
                             "email"] for x in value))
gflags.RegisterValidator("reminder",
                         lambda value: all(
                             gcal.parse_reminder(x) for x in value))
gflags.RegisterValidator("color_owner",
                         lambda value: get_color(value) is not None)
gflags.RegisterValidator("color_writer",
                         lambda value: get_color(value) is not None)
gflags.RegisterValidator("color_reader",
                         lambda value: get_color(value) is not None)
gflags.RegisterValidator("color_freebusy",
                         lambda value: get_color(value) is not None)
gflags.RegisterValidator("color_date",
                         lambda value: get_color(value) is not None)
gflags.RegisterValidator("color_now_marker",
                         lambda value: get_color(value) is not None)
gflags.RegisterValidator("color_border",
                         lambda value: get_color(value) is not None)

gflags.ADOPT_module_key_flags(gflags)


def version():
    print(__program__,  __version__,  ' (', __author__,  ')')


def usage(expanded=False):
    print(__doc__ % sys.argv[0])
    if expanded:
        print(FLAGS.MainModuleHelp())


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
    return
    print_msg(colors.CLR_YLW(), msg)


def print_err_msg(msg):
    print_msg(colors.CLR_BRRED(), msg)


def print_msg(color, msg):
    if colors.CLR.use_color:
        msg = str(color) + msg + str(colors.CLR_NRM())
    sys.stdout.write(msg)


def main():
    try:
        argv = sys.argv
        if os.path.exists(os.path.expanduser('~/.gcalclirc')):
            # We want .gcalclirc to be sourced before any other --flagfile
            # params since we may be told to use a specific config folder, we
            # need to store generated argv in temp variable
            tmpArgv = [argv[0], "--flagfile=~/.gcalclirc"] + argv[1:]
        else:
            tmpArgv = argv
        args = FLAGS(tmpArgv)
    except gflags.FlagsError as e:
        print_err_msg(str(e))
        usage(True)
        sys.exit(1)

    if FLAGS.config_folder:
        if not os.path.exists(os.path.expanduser(FLAGS.config_folder)):
            os.makedirs(os.path.expanduser(FLAGS.config_folder))
        if os.path.exists(os.path.expanduser("%s/gcalclirc" %
                                             FLAGS.config_folder)):
            if not FLAGS.includeRc:
                tmpArgv = argv + ["--flagfile=%s/gcalclirc" %
                                  FLAGS.config_folder, ]
            else:
                tmpArgv += ["--flagfile=%s/gcalclirc" % FLAGS.config_folder, ]

        FLAGS.Reset()
        args = FLAGS(tmpArgv)

    argv = tmpArgv

    if FLAGS.version:
        version()
        sys.exit(0)

    if FLAGS.help:
        usage(True)
        sys.exit(0)

    if FLAGS.helpshort:
        usage()
        sys.exit(0)

    if not FLAGS.color:
        colors.CLR.use_color = False

    if not FLAGS.lineart:
        gcal.ART.useArt = False

    if FLAGS.conky:
        colors.SetConkyColors()

    if FLAGS.locale:
        try:
            locale.setlocale(locale.LC_ALL, FLAGS.locale)
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

    if len(FLAGS.calendar) == 0:
        FLAGS.calendar = FLAGS.default_calendar

    cal_names = []
    cal_name_colors = []
    cal_colors = gcal.get_cal_colors(FLAGS.calendar)
    cal_names_filtered = []
    for cal_name in FLAGS.calendar:
        cal_name_simple = cal_name.split("#")[0]
        cal_names_filtered.append(cal_name_simple)
        cal_name_colors.append(cal_colors[cal_name_simple])
    cal_names = cal_names_filtered

    if 'all' in FLAGS.details or FLAGS.detail_all:
        if not FLAGS['detail_calendar'].present:
            FLAGS['detail_calendar'].value = True
        if not FLAGS['detail_location'].present:
            FLAGS['detail_location'].value = True
        if not FLAGS['detail_length'].present:
            FLAGS['detail_length'].value = True
        if not FLAGS['detail_reminders'].present:
            FLAGS['detail_reminders'].value = True
        if not FLAGS['detail_description'].present:
            FLAGS['detail_description'].value = True
        if not FLAGS['detail_url'].present:
            FLAGS['detail_url'].value = "long"
        if not FLAGS['detail_attendees'].present:
            FLAGS['detail_attendees'].value = True
        if not FLAGS['detail_attachments'].present:
            FLAGS['detail_attachments'].value = True
        if not FLAGS['detail_email'].present:
            FLAGS['detail_email'].value = True
    else:
        if 'calendar' in FLAGS.details:
            FLAGS['detail_calendar'].value = True
        if 'location' in FLAGS.details:
            FLAGS['detail_location'].value = True
        if 'attendees' in FLAGS.details:
            FLAGS['detail_attendees'].value = True
        if 'attachments' in FLAGS.details:
            FLAGS['detail_attachments'].value = True
        if 'length' in FLAGS.details:
            FLAGS['detail_length'].value = True
        if 'reminders' in FLAGS.details:
            FLAGS['detail_reminders'].value = True
        if 'description' in FLAGS.details:
            FLAGS['detail_description'].value = True
        if 'longurl' in FLAGS.details or 'url' in FLAGS.details:
            FLAGS['detail_url'].value = 'long'
        elif 'shorturl' in FLAGS.details:
            FLAGS['detail_url'].value = 'short'
        if 'attendees' in FLAGS.details:
            FLAGS['detail_attendees'].value = True
        if 'email' in FLAGS.details:
            FLAGS['detail_email'].value = True

    gci = gcal.GoogleCalendarInterface(
           cal_names=cal_names,
           cal_name_colors=cal_name_colors,
           military=FLAGS.military,
           detail_calendar=FLAGS.detail_calendar,
           detail_location=FLAGS.detail_location,
           detail_attendees=FLAGS.detail_attendees,
           detail_attachments=FLAGS.detail_attachments,
           detail_length=FLAGS.detail_length,
           detail_reminder=FLAGS.detail_reminders,
           detail_descr=FLAGS.detail_description,
           detail_descr_width=FLAGS.detail_description_width,
           detail_url=FLAGS.detail_url,
           detail_email=FLAGS.detail_email,
           ignore_started=not FLAGS.started,
           ignoreDeclined=not FLAGS.declined,
           calWidth=FLAGS.width,
           calMonday=FLAGS.monday,
           calOwnerColor=get_color(FLAGS.color_owner),
           calWriterColor=get_color(FLAGS.color_writer),
           calReaderColor=get_color(FLAGS.color_reader),
           calFreeBusyColor=get_color(FLAGS.color_freebusy),
           date_color=get_color(FLAGS.color_date),
           nowMarkerColor=get_color(FLAGS.color_now_marker),
           border_color=get_color(FLAGS.color_border),
           tsv=FLAGS.tsv,
           refresh_cache=FLAGS.refresh,
           use_cache=FLAGS.cache,
           config_folder=FLAGS.config_folder,
           client_id=FLAGS.client_id,
           client_secret=FLAGS.client_secret,
           defaultReminders=FLAGS.default_reminders,
           all_day=FLAGS.allday)

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

        if not FLAGS.tsv:
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

        if not FLAGS.tsv:
            sys.stdout.write('\n')

    elif args[0] == 'calw':
        if not FLAGS.width:
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
        if not FLAGS.width:
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

        gci.quick_add_event(args[1], reminder=FLAGS.reminder)

    elif (args[0] == 'add'):
        if FLAGS.prompt:
            if FLAGS.title is None:
                print_msg(colors.CLR_MAG(), "Title: ")
                FLAGS.title = input()
            if FLAGS.where is None:
                print_msg(colors.CLR_MAG(), "Location: ")
                FLAGS.where = input()
            if FLAGS.when is None:
                print_msg(colors.CLR_MAG(), "When: ")
                FLAGS.when = input()
            if FLAGS.duration is None:
                if FLAGS.allday:
                    print_msg(colors.CLR_MAG(), "Duration (days): ")
                else:
                    print_msg(colors.CLR_MAG(), "Duration (mins): ")
                FLAGS.duration = input()
            if FLAGS.description is None:
                print_msg(colors.CLR_MAG(), "Description: ")
                FLAGS.description = input()
            if not FLAGS.reminder:
                while 1:
                    print_msg(colors.CLR_MAG(),
                              "Enter a valid reminder or '.' to end: ")
                    r = input()
                    if r == '.':
                        break
                    n, m = gcal.parse_reminder(str(r))
                    FLAGS.reminder.append(str(n) + ' ' + m)

        # calculate "when" time:
        try:
            e_start, e_end = get_time_from_str(
                    FLAGS.when, FLAGS.duration, FLAGS.allday)
        except ValueError as exc:
            print_err_msg(str(exc))
            sys.exit(1)

        gci.add_event(FLAGS.title, FLAGS.where, e_start, e_end,
                      FLAGS.description, FLAGS.who,
                      FLAGS.reminder)

    elif args[0] == 'delete':
        eStart = None
        eEnd = None
        if len(args) < 2:
            print_err_msg('Error: invalid search string\n')
            sys.exit(1)
        elif len(args) == 4:  # search, start, end
            eStart = gci.date_parser.from_string(args[2])
            eEnd = gci.date_parser.from_string(args[3])
        elif len(args) == 3:  # search, start (default end)
            eStart = gci.date_parser.from_string(args[2])

        gci.delete_events(args[1], FLAGS.iamaexpert, eStart, eEnd)

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
                       args[2], use_reminders=FLAGS.use_reminders)
        elif len(args) == 2:  # minutes
            gci.Remind(int(args[1]), use_reminders=FLAGS.use_reminders)
        elif len(args) == 1:  # defaults
            gci.Remind(use_reminders=FLAGS.use_reminders)
        else:
            print_err_msg('Error: invalid remind arguments\n')
            sys.exit(1)

    elif args[0] == 'import':
        if len(args) == 1:  # stdin
            gci.ImportICS(FLAGS.verbose, FLAGS.dump, FLAGS.reminder)
        elif len(args) == 2:  # ics file
            gci.ImportICS(FLAGS.verbose, FLAGS.dump, FLAGS.reminder, args[1])
        else:
            print_err_msg('Error: invalid import arguments\n')
            sys.exit(1)


def SIGINT_handler(signum, frame):
    print_err_msg('Signal caught, bye!\n')
    sys.exit(1)


signal.signal(signal.SIGINT, SIGINT_handler)

if __name__ == '__main__':
    main()
