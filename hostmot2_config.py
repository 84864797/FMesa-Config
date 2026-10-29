"""HostMot2 load options follow PNCconf's discovered-resource branches."""

def module_count(c,name,tag=None):
    modules=(c.get('discovery') or {}).get('modules',{})
    value=modules.get(name,modules.get(str(tag),0) if tag is not None else 0)
    return value.get('count',0) if isinstance(value,dict) else value


def serial_option(c):
    if c.get('remote_enabled',True):return ' sserial_port_0='+c['sserial']
    discovered=c.get('discovery') or {}
    present=module_count(c,'sserial',193) or module_count(c,'sserialb',198)
    present=present or any(p.get('secondarymodulename','').lower() in ('sserial','sserialb') for p in discovered.get('pins',[]))
    # PNCconf emits one option per configured/discovered serial port.
    return ' sserial_port_0=xxxxxxxx' if present else ''


def dpll_settings(c):
    if c['stepgens'] and (module_count(c,'dpll',26) or module_count(c,'hm2dpll')):
        return [f'setp {c["host"]}.dpll.01.timer-us {c.get("dpll_timer_us",-50)}',
                f'setp {c["host"]}.stepgen.timer-number 1']
    return []
