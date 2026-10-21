import json
import unittest
from serial_protocol import DriveGate, ForwardPressGate, parse_sample

def frame(**changes):
    data=dict(v=1,type='state',boot=123,seq=1,ms=20,raw=1500,adc=1500,calibrated=True,notch='N')
    data.update(changes)
    return json.dumps(data)

class ProtocolTests(unittest.TestCase):
    def test_valid_and_uncalibrated(self):
        self.assertEqual(parse_sample(frame()).notch,'N')
        self.assertFalse(parse_sample(frame(calibrated=False,notch='--')).calibrated)
    def test_reject_broken_frames(self):
        for data in ['{','{}','[]',frame(raw=True),frame(adc=4096),frame(v=2),frame(seq=-1),
                     frame(calibrated=1),frame(notch='P6'),frame(calibrated=False,notch='P1')]:
            with self.subTest(data=data),self.assertRaises(ValueError):parse_sample(data)
    def test_ack_is_not_state(self):
        self.assertIsNone(parse_sample('{"v":1,"type":"ack","message":"ready"}'))
    def test_not_armed_by_data(self):
        gate=DriveGate();gate.receive(parse_sample(frame(notch='P5')),0)
        self.assertEqual(gate.output(0),'N')
        with self.assertRaises(ValueError):gate.arm(0)
    def test_neutral_arm_then_absolute_changes(self):
        gate=DriveGate();gate.receive(parse_sample(frame()),0);gate.arm(0)
        gate.receive(parse_sample(frame(seq=2,notch='P3')),0.1)
        self.assertEqual(gate.output(0.1),'P3')
    def test_timeout_neutral_and_no_automatic_rearm(self):
        gate=DriveGate();gate.receive(parse_sample(frame()),0);gate.arm(0)
        self.assertEqual(gate.output(.6),'N');self.assertFalse(gate.armed)
        gate.receive(parse_sample(frame(seq=2,notch='P5')),.7)
        self.assertEqual(gate.output(.7),'N')
    def test_gap_neutral_even_if_new_frame_arrives_before_tick(self):
        gate=DriveGate();gate.receive(parse_sample(frame()),0);gate.arm(0)
        gate.receive(parse_sample(frame(seq=2,notch='P1')),1)
        self.assertFalse(gate.armed)
    def test_reset_disarms(self):
        gate=DriveGate();gate.receive(parse_sample(frame()),0);gate.arm(0)
        gate.receive(parse_sample(frame(boot=456,notch='P5')),.1)
        self.assertEqual(gate.output(.1),'N')
    def test_sequence_replay_and_wrap(self):
        gate=DriveGate();gate.receive(parse_sample(frame(seq=0xffffffff)),0)
        self.assertTrue(gate.receive(parse_sample(frame(seq=0)),.1))
        self.assertFalse(gate.receive(parse_sample(frame(seq=0)),.2))
        self.assertFalse(gate.receive(parse_sample(frame(seq=0xffffffff)),.2))
        self.assertEqual(gate.received,.1)
    def test_calibration_disarms(self):
        gate=DriveGate();gate.receive(parse_sample(frame()),0);gate.arm(0)
        gate.receive(parse_sample(frame(seq=2,calibrated=False,notch='--')),.1)
        self.assertFalse(gate.armed)
    def test_arm_requires_fresh_data(self):
        with self.assertRaises(ValueError):DriveGate().arm(0)
        gate=DriveGate();gate.receive(parse_sample(frame()),0)
        with self.assertRaises(ValueError):gate.arm(1)
    def test_queued_old_frame_keeps_original_arrival_time(self):
        gate=DriveGate();gate.receive(parse_sample(frame()),0);gate.arm(0)
        # UI drains a queued frame much later; receive time is captured by Reader.
        gate.receive(parse_sample(frame(seq=2,notch='P5')),.1)
        self.assertEqual(gate.output(1),'N')
        self.assertFalse(gate.armed)

class ForwardTests(unittest.TestCase):
    def sample(self,count=0,pressed=False,**kw):
        return parse_sample(frame(forward_count=count,forward_pressed=pressed,**kw))
    def test_forward_fields_are_strict(self):
        for fields in ({'forward_pressed':1},{'forward_count':True},{'forward_count':-1}):
            with self.assertRaises(ValueError):parse_sample(frame(**fields))
    def test_press_once_no_hold_repeat(self):
        g=ForwardPressGate()
        self.assertFalse(g.receive(self.sample(),0,0,True))
        self.assertTrue(g.receive(self.sample(1,True),.1,.1,True))
        self.assertFalse(g.receive(self.sample(1,True),.2,.2,True))
        self.assertFalse(g.receive(self.sample(1,False),.3,.3,True))
        self.assertTrue(g.receive(self.sample(2,True),.4,.4,True))
    def test_no_replay_after_arm_or_first_connection(self):
        g=ForwardPressGate()
        self.assertFalse(g.receive(self.sample(1,True),0,0,True))
        self.assertFalse(g.receive(self.sample(2,True),.1,.1,False))
        self.assertFalse(g.receive(self.sample(2,True),.2,.2,True))
    def test_stale_non_neutral_and_reset_are_consumed(self):
        for changed,arrival,now in [(dict(notch='P1'),.1,.1),({},.1,1),
                                    (dict(boot=456),.1,.1),
                                    (dict(calibrated=False,notch='--'),.1,.1)]:
            with self.subTest(changed=changed):
                g=ForwardPressGate();g.receive(self.sample(),0,0,True)
                self.assertFalse(g.receive(self.sample(1,True,**changed),arrival,now,True))
    def test_skipped_presses_not_replayed_and_wrap_supported(self):
        g=ForwardPressGate();g.receive(self.sample(),0,0,True)
        self.assertFalse(g.receive(self.sample(2,True),.1,.1,True))
        g=ForwardPressGate();g.receive(self.sample(0xffffffff),0,0,True)
        self.assertTrue(g.receive(self.sample(0,True),.1,.1,True))

if __name__=='__main__':unittest.main()
