from gcalcli.utils import get_time_from_str


def test_get_time_from_str():
    begin_2018_gmt = '2018-01-01T00:00:00+00:00'
    two_hrs_later = '2018-01-01T02:00:00+00:00'
    assert (begin_2018_gmt, two_hrs_later) == \
        get_time_from_str(begin_2018_gmt, e_duration=120)
