#!/usr/bin/python3
"""Mesa / SD通信监控。用系统Python运行，依赖Debian的python3-tk及LinuxCNC hal。"""
import argparse
import json
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from sserial_monitor_core import MonitorState, PORT, REMOTE

class HalReader:
    def __init__(self,host):
        import hal
        self.component=hal.component('mesa_sd_monitor_'+str(os.getpid()))
        self.component.ready()
        self.hal=hal;self.host=host;self.names=[];self.remotes=[];self.next_scan=0

    def read(self):
        if time.monotonic()>=self.next_scan:
            # Our component exports no pins and never modifies the machine's HAL values.
            pins=self.hal.get_info_pins()
            params=self.hal.get_info_params()
            records=pins+params
            all_names=[p['NAME'] for p in records if p['NAME'].startswith(self.host+'.')]
            self.names=sorted({n for n in all_names if PORT.match(n)})
            self.remotes=sorted({m[1] for n in all_names if (m:=REMOTE.match(n))})
            self.next_scan=time.monotonic()+1
        if not self.names:
            raise RuntimeError('未找到此Mesa主卡的Smart Serial状态引脚。请先启动LinuxCNC并核对HAL前缀。')
        return {name:self.hal.get_value(name) for name in self.names}

    def close(self):self.component.exit()

class Window:
    def __init__(self,root,demo=False):
        self.root=root;self.demo=demo;self.state=MonitorState();self.lock=threading.Lock()
        self.stop=threading.Event();self.thread=None;self.displayed_events=0
        root.title('Mesa / SD 智能串口通信监控 · 实时采样'+('【演示数据】' if demo else ''));root.geometry('1130x710')
        panel=ttk.Frame(root,padding=12);panel.pack(fill='both',expand=True)
        bar=ttk.Frame(panel);bar.pack(fill='x')
        ttk.Label(bar,text='Mesa HAL前缀').pack(side='left')
        self.host=tk.StringVar(value='hm2_7i92.0');self.host_entry=ttk.Entry(bar,textvariable=self.host,width=23);self.host_entry.pack(side='left',padx=6)
        ttk.Label(bar,text='采样间隔 / ms').pack(side='left')
        self.interval=tk.StringVar(value='10');self.interval_entry=ttk.Entry(bar,textvariable=self.interval,width=6);self.interval_entry.pack(side='left',padx=6)
        self.start_button=ttk.Button(bar,text='开始监控',command=self.start);self.start_button.pack(side='left',padx=4)
        ttk.Button(bar,text='停止',command=self.stop.set).pack(side='left',padx=4)
        ttk.Button(bar,text='导出报告',command=self.export).pack(side='right')
        self.status=tk.StringVar(value='等待开始。先打开LinuxCNC，再开始监控。')
        self.status_label=tk.Label(panel,textvariable=self.status,anchor='w',font=('',15),fg='#555555');self.status_label.pack(fill='x',pady=12)
        self.summary=tk.StringVar(value='');ttk.Label(panel,textvariable=self.summary).pack(fill='x')
        self.remote_text=tk.StringVar(value='识别到的SD板：尚未读取');ttk.Label(panel,textvariable=self.remote_text).pack(fill='x',pady=6)
        columns=('port','status','state','score','rises','peak','samples')
        self.table=ttk.Treeview(panel,columns=columns,show='headings',height=6)
        for col,label,width in zip(columns,('Smart Serial端口','当前状态','状态值','当前错误积分','观察上升次数¹','最高积分','采样数'),(245,210,70,105,110,80,80)):
            self.table.heading(col,text=label);self.table.column(col,width=width,stretch=col in ('port','status'))
        self.table.pack(fill='x')
        ttk.Label(panel,text='¹ 上升次数是观察下限，不是精确累计错误数。错误积分可因成功通信而下降；同一端口的多块从板共用端口统计。',wraplength=1060).pack(fill='x',pady=8)
        ttk.Label(panel,text='此工具只读HAL，不发送控制或烧写命令。无法捕获全部串口帧、CRC细节，也无法确认物理输出是否执行。',wraplength=1060).pack(fill='x')
        ttk.Label(panel,text='事件日志（检测开始时的已有错误积分单独记录）').pack(anchor='w',pady=(10,3))
        self.log=tk.Text(panel,height=10,state='disabled',font=('Monospace',10));self.log.pack(fill='both',expand=True)
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(200,self.refresh)

    def start(self):
        if self.thread and self.thread.is_alive():return
        try:
            interval=float(self.interval.get())/1000
            if not .005<=interval<=5:raise ValueError('采样间隔需为5～5000毫秒')
            host=self.host.get().strip()
            import re
            if not re.fullmatch(r'hm2_[A-Za-z0-9_]+\.\d+',host):raise ValueError('请输入主卡HAL前缀，例如hm2_7i92.0')
            reader=None if self.demo else HalReader(host)
        except Exception as exc:messagebox.showerror('无法启动',str(exc));return
        self.stop.clear();self.start_button.config(state='disabled');self.host_entry.config(state='disabled');self.interval_entry.config(state='disabled')
        with self.lock:self.state=MonitorState()
        self.displayed_events=0;self.log.config(state='normal');self.log.delete('1.0','end');self.log.config(state='disabled')
        self.thread=threading.Thread(target=self.sample,args=(reader,host,interval),daemon=True);self.thread.start()

    def sample(self,reader,host,interval):
        start=time.monotonic()
        while not self.stop.is_set():
            tick=time.monotonic()
            try:
                if self.demo:
                    elapsed=tick-start;phase=int(elapsed)%12
                    values={host+'.sserial.port-0.run':True,host+'.sserial.port-0.state':3,
                            host+'.sserial.port-0.fault-count':10 if phase in (4,8) else 0}
                    remotes=[host+'.SD01.0.0（演示）']
                else:values=reader.read();remotes=reader.remotes
                with self.lock:self.state.remotes=remotes;self.state.update(values)
            except Exception as exc:
                with self.lock:self.state.failed(str(exc))
                self.stop.wait(max(interval,.5));continue
            self.stop.wait(max(0,interval-(time.monotonic()-tick)))
        if reader:reader.close()

    def refresh(self):
        with self.lock:report=self.state.report();events=list(self.state.events);port_reports=dict(report['ports'])
        active=bool(self.thread and self.thread.is_alive())
        if not active:
            self.start_button.config(state='normal');self.host_entry.config(state='normal');self.interval_entry.config(state='normal')
        if report['last_error']:text=report['last_error'];color='#aa6500'
        elif not active:text='监控已停止（表中为历史值）' if self.thread else '等待开始。先打开LinuxCNC，再开始监控。';color='#555555'
        elif not port_reports:text='正在读取HAL…';color='#555555'
        elif any(p['score'] is not None and p['score']>0 for p in port_reports.values()):text='检测到通信错误积分';color='#b00020'
        elif all(p['status']=='暂未观察到异常' for p in port_reports.values()):text='当前采样暂未观察到通信异常';color='#167238'
        else:text='端口状态需检查（见下表）';color='#aa6500'
        if self.demo:text='【演示数据】'+text
        self.status.set(text);self.status_label.config(fg=color)
        latest=max((p['last_seen'] for p in port_reports.values()),default=0)
        heartbeat=time.strftime('%H:%M:%S',time.localtime(latest)) if latest else '尚无数据'
        self.summary.set(f'最近采样：{heartbeat}    积分上升：{sum(p["rises"] for p in port_reports.values())} 次    读取失败：{report["read_failures"]} 次    最大采样间隔：{report["max_observed_sample_gap_seconds"]*1000:.1f} ms')
        self.remote_text.set('识别到的SD板：'+('；'.join(report['remotes']) or '未识别到SD01/SD02；引脚名称存在也不代表当前链路在线'))
        self.table.delete(*self.table.get_children())
        for port,p in port_reports.items():self.table.insert('','end',values=(port,p['status'],p['state'] if p['state'] is not None else '未知',p['score'] if p['score'] is not None else '未知',p['rises'],p['peak'],p['samples']))
        total=len(events)+report['dropped_events']
        new=events[max(0,self.displayed_events-report['dropped_events']):]
        if new:
            self.log.config(state='normal')
            for event in new:self.log.insert('end',time.strftime('%H:%M:%S',time.localtime(event['time']))+' '+json.dumps(event,ensure_ascii=False)+'\n')
            if int(self.log.index('end-1c').split('.')[0])>1000:self.log.delete('1.0','200.0')
            self.log.see('end');self.log.config(state='disabled')
        self.displayed_events=total;self.root.after(200,self.refresh)

    def export(self):
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile='mesa-sserial-'+time.strftime('%Y%m%d-%H%M%S')+'.json',filetypes=[('JSON报告','*.json')])
        if not path:return
        with self.lock:report=json.loads(json.dumps(self.state.report()))
        report.update(demo=self.demo,host=self.host.get(),requested_interval_ms=self.interval.get())
        try:
            with open(path,'w',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
        except OSError as exc:messagebox.showerror('保存失败',str(exc))

    def close(self):self.stop.set();self.root.destroy()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--demo',action='store_true',help='仅使用演示数据，不读取HAL')
    args=parser.parse_args();root=tk.Tk();window=Window(root,args.demo);root.after(200,window.start);root.mainloop()

if __name__=='__main__':main()
