"""Read-only Smart Serial monitoring; error-count is a decaying score, not a total."""
import re
import time
from dataclasses import dataclass, field

PORT = re.compile(r'^(hm2_[\w]+\.\d+\.sserial\.port-\d+)\.(.+)$')
REMOTE = re.compile(r'^(hm2_[\w]+\.\d+\.(?:sd01|sd02)\.\d+\.\d+)\.', re.I)

@dataclass
class PortStats:
    samples: int = 0
    rises: int = 0
    positive_samples: int = 0
    peak: int = 0
    previous: int | None = None
    fields: dict = field(default_factory=dict)
    last_seen: float = 0

    def update(self, fields, now):
        self.fields = dict(fields); self.last_seen = now; self.samples += 1
        value = fields.get('error-count', fields.get('fault-count'))
        event = None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = int(value)
            if value > 0:self.positive_samples += 1
            self.peak = max(self.peak, value)
            if self.previous is not None and value > self.previous:
                self.rises += 1
                event = dict(time=now, kind='score-rise', before=self.previous, after=value)
            elif self.previous is None and value > 0:
                event = dict(time=now, kind='initial-nonzero-score', value=value)
            self.previous = value
        return event

    def interrupted(self):
        # A reload/disconnect breaks continuity; do not count the next baseline as a new error.
        self.previous = None

    def report(self):
        value=self.fields.get('error-count',self.fields.get('fault-count'))
        state=self.fields.get('port_state',self.fields.get('run_state',self.fields.get('state')))
        run=self.fields.get('run')
        if run is False:status='端口未启用'
        elif isinstance(value,(int,float)) and value>0:status='检测到通信错误积分'
        elif state is not None and state!=3:status='端口不在正常运行态'
        elif value is None:status='未提供错误积分，无法判断'
        elif state is None:status='积分为0；运行状态未提供'
        else:status='暂未观察到异常'
        return dict(status=status,score=value,state=state,run=run,rises=self.rises,
                    peak=self.peak,samples=self.samples,positive_samples=self.positive_samples,
                    fields=self.fields,last_seen=self.last_seen)

class MonitorState:
    def __init__(self):
        self.ports={};self.remotes=[];self.events=[];self.dropped_events=0
        self.last_error='';self.started=time.time();self.read_failures=0;self.max_gap=0;self.last_sample=None

    def update(self, values, now=None):
        now=time.time() if now is None else now
        if self.last_sample is not None:self.max_gap=max(self.max_gap,now-self.last_sample)
        if self.last_error:self.add_event(dict(time=now,kind='hal-read-recovered'))
        self.last_sample=now;self.last_error=''
        grouped={}
        for name,value in values.items():
            match=PORT.match(name)
            if match:grouped.setdefault(match[1],{})[match[2]]=value
        for port,stats in self.ports.items():
            if port not in grouped:
                if stats.fields:self.add_event(dict(time=now,kind='port-disappeared',port=port))
                stats.interrupted();stats.fields={}
        for port,fields in grouped.items():
            stats=self.ports.setdefault(port,PortStats())
            previous=stats.fields
            for key in ('run','state','run_state','port_state','port_state2','port_state3'):
                if key in previous and key in fields and previous[key]!=fields[key]:
                    self.add_event(dict(time=now,kind='port-state-change',port=port,field=key,before=previous[key],after=fields[key]))
            event=stats.update(fields,now)
            if event:self.add_event(dict(port=port,**event))
        return grouped

    def failed(self,message):
        if str(message)!=self.last_error:self.add_event(dict(time=time.time(),kind='hal-read-failed',message=str(message)))
        self.read_failures+=1;self.last_error=str(message)
        self.last_sample=None
        for stats in self.ports.values():stats.interrupted()

    def add_event(self,event):
        self.events.append(event)
        if len(self.events)>10000:
            self.events.pop(0);self.dropped_events+=1

    def report(self):
        return dict(started=self.started,read_failures=self.read_failures,last_error=self.last_error,
                    max_observed_sample_gap_seconds=self.max_gap,remotes=self.remotes,
                    ports={name:stats.report() for name,stats in self.ports.items()},
                    events=self.events,dropped_events=self.dropped_events,
                    interpretation='error-count/fault-count为会衰减的错误积分；上升次数为采样观察值，可能漏掉采样之间的错误，不能作为精确累计错误数。端口统计不能区分同端口多个从板。')
