import calendar
from datetime import datetime, timedelta
import time

# Required 3rd party libraries
try:
    from dateutil.tz import tzlocal
    from dateutil.parser import parse
except ImportError as e:
    import sys
    print("ERROR: Missing module - {}".format(e.args[0]))
    sys.exit(1)


# If they have parsedatetime, we'll use it for fuzzy datetime comparison.  If
# not, we just return a fake failure every time and use only dateutil.
try:
    from parsedatetime import parsedatetime
except Exception:
    class parsedatetime:
        class Calendar:
            def parse(self, string):
                return ([], 0)


class DateTimeParser:
    def __init__(self):
        self.pdtCalendar = parsedatetime.Calendar()

    def from_string(self, eWhen):
        defaultDateTime = datetime.now(tzlocal()).replace(hour=0,
                                                          minute=0,
                                                          second=0,
                                                          microsecond=0)

        try:
            eTimeStart = parse(eWhen, default=defaultDateTime)
        except Exception:
            struct, result = self.pdtCalendar.parse(eWhen)
            if not result:
                raise ValueError("Date and time is invalid")
            eTimeStart = datetime.fromtimestamp(time.mktime(struct), tzlocal())

        return eTimeStart


def days_since_epoch(dt):
    # Because I hate magic numbers
    __DAYS_IN_SECONDS__ = 24 * 60 * 60
    return calendar.timegm(dt.timetuple()) / __DAYS_IN_SECONDS__


def get_time_from_str(e_when, e_duration=0, allday=False):
    dtp = DateTimeParser()

    try:
        e_time_start = dtp.from_string(e_when)
    except Exception:
        raise ValueError('Date and time is invalid.')

    if allday:
        try:
            e_time_stop = e_time_start + timedelta(days=float(e_duration))
        except Exception:
            raise ValueError('Duration time (days) is invalid.')

        s_time_start = e_time_start.date().isoformat()
        s_time_stop = e_time_stop.date().isoformat()

    else:
        try:
            e_time_stop = e_time_start + timedelta(minutes=float(e_duration))
        except Exception:
            raise ValueError('Duration time (minutes) is invalid.')

        s_time_start = e_time_start.isoformat()
        s_time_stop = e_time_stop.isoformat()

    return s_time_start, s_time_stop
