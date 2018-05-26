from gcalcli import colors
from gcalcli.gcal import GoogleCalendarInterface
from gcalcli.cli import print_msg
from gcalcli.utils import get_time_from_str
from apiclient.discovery import HttpMock, build
import pytest
import os
from json import load

TEST_DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + '/data'


def mocked_calendar_service(self):
    http = HttpMock(
            TEST_DATA_DIR + '/cal_service_discovery.json', {'status': '200'})
    if not self.cal_service:
        self.cal_service = build(
                serviceName='calendar', version='v3', http=http)
    return self.cal_service


def mocked_calendar_list(self):
    http = HttpMock(TEST_DATA_DIR + '/cal_list.json', {'status': '200'})
    request = self._cal_service().calendarList().list()
    cal_list = request.execute(http=http)
    self.all_cals = [cal for cal in cal_list['items']]


@pytest.fixture
def gcal(monkeypatch):
    monkeypatch.setattr(
            GoogleCalendarInterface, '_cal_service', mocked_calendar_service)
    monkeypatch.setattr(
            GoogleCalendarInterface, '_get_cached', mocked_calendar_list)
    return GoogleCalendarInterface(use_cache=False)


# TODO: These are more like placeholders for proper unit tests
#       We just try the commands and make sure no errors occur.
def test_list(gcal):
    # test data has 6 cals
    with open(TEST_DATA_DIR + '/cal_list.json') as cl:
        assert len(load(cl)['items']) == len(gcal.all_cals)
    # TODO: should test the table formatting
    # for now, just assert that there's no error, ha!
    gcal.list_all_calendars()


def test_agenda(gcal):
    gcal.agenda_query()


def test_cal_query(gcal):
    gcal.agenda_query('calw')
    gcal.agenda_query('calm')


# @pytest.fixture
# def test_search(gcal, capsys):
#     # gcal.ignore_started = True
#     gcal.text_query('jam')
#     captured = capsys.readouterr()
#     assert captured == ""


@pytest.fixture
def test_print_msg(capsys):
    print_msg(colors.CLR_BRRED(), 'test')
    captured = capsys.readouterr()
    assert captured == str(colors.CLR_BRRED()) + 'test' + str(colors.CLR_NRM())


def test_get_time_from_str():
    begin_2018_gmt = '2018-01-01T00:00:00+00:00'
    two_hrs_later = '2018-01-01T02:00:00+00:00'
    assert (begin_2018_gmt, two_hrs_later) == \
        get_time_from_str(begin_2018_gmt, e_duration=120)
