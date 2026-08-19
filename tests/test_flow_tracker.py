"""Tests for the flow rate derived from the cumulative water counter."""

from datetime import datetime, timedelta

from flow_tracker import FlowTracker

START = datetime(2024, 6, 21, 8, 0, 0)


def test_no_value_before_two_samples():
    tracker = FlowTracker(timedelta(seconds=120))
    tracker.add(1000, START)
    assert tracker.flow_l_per_min is None
    assert tracker.is_flowing is False


def test_steady_draw_is_converted_to_litres_per_minute():
    tracker = FlowTracker(timedelta(seconds=120))
    tracker.add(1000, START)
    tracker.add(1010, START + timedelta(seconds=60))
    assert tracker.flow_l_per_min == 10.0
    assert tracker.is_flowing is True


def test_unchanged_counter_reports_zero():
    tracker = FlowTracker(timedelta(seconds=120))
    tracker.add(1000, START)
    tracker.add(1000, START + timedelta(seconds=60))
    assert tracker.flow_l_per_min == 0.0
    assert tracker.is_flowing is False


def test_window_discards_samples_that_are_fully_aged_out():
    tracker = FlowTracker(timedelta(seconds=60))
    for offset, total in ((0, 1000), (30, 1000), (60, 1000), (90, 1030)):
        tracker.add(total, START + timedelta(seconds=offset))
    # Only the trailing 60 s window is averaged: 30 litres over 60 s.
    assert tracker.flow_l_per_min == 30.0


def test_counter_reset_clears_history():
    tracker = FlowTracker(timedelta(seconds=120))
    tracker.add(5000, START)
    tracker.add(10, START + timedelta(seconds=30))
    assert tracker.flow_l_per_min is None


def test_duplicate_timestamps_do_not_divide_by_zero():
    tracker = FlowTracker(timedelta(seconds=120))
    tracker.add(1000, START)
    tracker.add(1005, START)
    assert tracker.flow_l_per_min is None
