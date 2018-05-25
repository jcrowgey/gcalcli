from gcalcli.gcalcli import (
        GoogleCalendarInterface, print_msg, CLR_BRRED, CLR_NRM,
        get_time_from_str, FLAGS)
from apiclient.discovery import HttpMock, build
import pytest
import os
from json import load

TEST_DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + '/data'


def mocked_calendar_service(self):
    http = HttpMock(
            TEST_DATA_DIR + '/cal_service_discovery.json', {'status': '200'})
    self._cal_service = build(serviceName='calendar', version='v3', http=http)
    return self._cal_service


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


# command tests
def test_list(gcal):
    # test data has 6 cals
    with open(TEST_DATA_DIR + '/cal_list.json') as cl:
        assert len(load(cl)['items']) == len(gcal.all_cals)
    # TODO: should test the table formatting
    # for now, just assert that there's no error, ha!
    # assert gcal.list_all_calendars()


# @pytest.fixture
# def test_search(gcal, capsys):
#     # gcal.ignore_started = True
#     gcal.text_query('jam')
#     captured = capsys.readouterr()
#     assert captured == ""


@pytest.fixture
def test_print_msg(capsys):
    print_msg(CLR_BRRED(), 'test')
    captured = capsys.readouterr()
    assert captured == str(CLR_BRRED()) + 'test' + str(CLR_NRM())


def test_get_time_from_str():
    FLAGS([])
    begin_2018_gmt = '2018-01-01T00:00:00+00:00'
    two_hrs_later = '2018-01-01T02:00:00+00:00'
    assert (begin_2018_gmt, two_hrs_later) == \
        get_time_from_str(begin_2018_gmt, e_duration=120)
