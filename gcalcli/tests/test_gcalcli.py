from gcalcli.gcalcli import GoogleCalendarInterface
from apiclient.discovery import Resource, HttpMock, build
import pytest
import os

TEST_DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + '/data'



def mocked_calendar_service(self):
    http = HttpMock(TEST_DATA_DIR + '/cal_service_discovery.json', {'status': '200'})
    self._cal_service = build(serviceName='calendar', version='v3', http=http)
    return self._cal_service


def mocked_calendar_list(self):
    http = HttpMock(TEST_DATA_DIR + '/cal_list.json', {'status': '200'})
    request = self._cal_service().calendarList().list()
    cal_list = request.execute(http=http)
    self.all_cals = [cal for cal in cal_list['items']]


@pytest.fixture
def gcal(monkeypatch):
    monkeypatch.setattr(GoogleCalendarInterface, '_cal_service',
            mocked_calendar_service)
    monkeypatch.setattr(GoogleCalendarInterface, '_get_cached',
            mocked_calendar_list)
    return GoogleCalendarInterface(use_cache=False)
    

def test_list(gcal):
    assert 6 == len(gcal.all_cals)
    # assert gcal.list_all_calendars()
