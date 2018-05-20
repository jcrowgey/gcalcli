from gcalcli.gcalcli import GoogleCalendarInterface
from apiclient.discovery import Resource, HttpMock, build
import pytest


def mocked_calendar_service(self):
    http = HttpMock('data/cal_service_discovery.json', {'status': '200'})
    self._cal_service = build(serviceName='calendar', version='v3', http=http)
    return self._cal_service


def mocked_calendar_list(self):
    http = HttpMock('data/cal_list.json', {'status': '200'})
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
    gcal.list_all_calendars()
