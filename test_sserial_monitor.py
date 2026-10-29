import unittest
from sserial_monitor_core import MonitorState, PortStats

class MonitorTest(unittest.TestCase):
    def test_actual_linuxcnc_port_state_name(self):
        p=PortStats();p.update({'fault-count':0,'port_state':3,'run':True},1)
        self.assertEqual(p.report()['state'],3)
        self.assertEqual(p.report()['status'],'暂未观察到异常')
    def test_decay_is_not_a_cumulative_error_counter(self):
        p=PortStats()
        for i,value in enumerate([0,10,9,8,18,0]):p.update({'error-count':value,'state':3,'run':True},i)
        self.assertEqual(p.rises,2);self.assertEqual(p.peak,18)
        self.assertEqual(p.report()['status'],'暂未观察到异常')
    def test_nonzero_initial_read_not_counted_as_new_error(self):
        p=PortStats();event=p.update({'fault-count':10},1)
        self.assertEqual(event['kind'],'initial-nonzero-score');self.assertEqual(p.rises,0)
        p.interrupted();p.update({'fault-count':30},2);self.assertEqual(p.rises,0)
    def test_no_error_pin_does_not_report_healthy(self):
        p=PortStats();p.update({'run':True,'state':3},1)
        self.assertIn('无法判断',p.report()['status'])
    def test_failed_read_breaks_baseline_and_records_recovery(self):
        m=MonitorState();name='hm2_7i92.0.sserial.port-0.fault-count'
        m.update({name:0},1);m.failed('HAL unavailable');m.update({name:100},2)
        self.assertEqual(m.report()['ports'][name.rsplit('.',1)[0]]['rises'],0)
        self.assertTrue(any(e['kind']=='hal-read-recovered' for e in m.events))
    def test_ports_kept_separate_and_disappearance_does_not_reuse_baseline(self):
        m=MonitorState();p0='hm2_7i92.0.sserial.port-0';p1='hm2_7i92.0.sserial.port-1'
        m.update({p0+'.error-count':0,p1+'.error-count':0,p0+'.state':3},1)
        m.update({p0+'.error-count':10,p1+'.error-count':0,p0+'.state':0},2)
        self.assertEqual(m.ports[p0].rises,1);self.assertEqual(m.ports[p1].rises,0)
        m.update({},3);m.update({p0+'.error-count':50},4)
        self.assertEqual(m.ports[p0].rises,1)
        self.assertTrue(any(e['kind']=='port-disappeared' for e in m.events))
    def test_event_history_is_bounded_but_totals_are_retained(self):
        m=MonitorState()
        for i in range(10005):m.add_event({'time':i})
        self.assertEqual(len(m.events),10000);self.assertEqual(m.dropped_events,5)

if __name__=='__main__':unittest.main()
