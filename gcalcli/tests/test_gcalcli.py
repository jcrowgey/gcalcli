from gcalcli import colors
from gcalcli.gcal import GoogleCalendarInterface
from gcalcli.cli import print_msg, debug_print, get_cal_colors, parse_args
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
def test_list(gcal, capsys):
    with open(TEST_DATA_DIR + '/cal_list.json') as cl:
        cal_count = len(load(cl)['items'])

    # test data has 6 cals
    assert cal_count == len(gcal.all_cals)

    # color state is being stored in the colors class.
    # ugh, is this java?!
    colors.CLR.use_color = False
    expected_header = ''' Access  Title\n'''

    gcal.list_all_calendars()
    captured = capsys.readouterr()
    assert captured.out.startswith(expected_header)

    # +3 cos one for the header, one for the '----' decorations,
    # and one for the eom
    assert len(captured.out.split('\n')) == cal_count + 3


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
def test_parse_args():
    parse_args(argv=[])


def test_print_msg(capsys):
    colors.CLR.use_color = True
    print_msg(colors.CLR_BRRED(), 'test')
    captured = capsys.readouterr()
    expected = str(colors.CLR_BRRED()) + 'test' + str(colors.CLR_NRM())
    assert captured.out == expected


@pytest.fixture
def test_debug_print(capsys):
    colors.CLR.use_color = True
    debug_print('test')
    captured = capsys.readouterr()
    assert captured == str(colors.CLR_YLW()) + 'test' + str(colors.CLR_NRM())


def test_get_cal_colors():
    test_cal = 'testcal@gmail.com'
    no_color_reply = {test_cal: None}
    assert no_color_reply == get_cal_colors([test_cal])

    reply = get_cal_colors([test_cal + '#red'])
    assert isinstance(reply[test_cal], colors.CLR_RED)

    assert no_color_reply == get_cal_colors([test_cal + '#notarealcolorname'])
