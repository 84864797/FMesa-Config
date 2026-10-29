"""INI defaults required by the supported LinuxCNC frontends."""

def settings(display,rpm):
    # PNCconf build_INI.py: QtDragon has indexed spindle fields; other
    # frontends receive only the unindexed override settings.
    result=dict(MIN_LINEAR_VELOCITY=.5,MIN_ANGULAR_VELOCITY=3,
                ANGULAR_INCREMENTS='1 5 10 30 45 90',CYCLE_TIME=100)
    if display in ('qtdragon','qtdragon_hd'):
        result.update(DEFAULT_SPINDLE_0_SPEED=500,MIN_SPINDLE_0_SPEED=100,
                      MAX_SPINDLE_0_SPEED=2500,MAX_SPINDLE_0_OVERRIDE=1.0,
                      MIN_SPINDLE_0_OVERRIDE=.5)
    else:
        result.update(MAX_SPINDLE_OVERRIDE=1.0,MIN_SPINDLE_OVERRIDE=.5)
    return result


def repair_ini(text,display,rpm):
    """Add missing UI settings, preserve mechanical data, comments and offsets."""
    import re
    values=settings(display,rpm)
    for kind in ('LINEAR','ANGULAR'):
        maximum=re.search(r'(?m)^\s*MAX_'+kind+r'_VELOCITY\s*=\s*([0-9.eE+-]+)',text)
        if maximum:
            values['MIN_'+kind+'_VELOCITY']=min(values['MIN_'+kind+'_VELOCITY'],float(maximum[1]))
    def patch_section(name,values,text):
        pattern=r'(?ms)^\['+re.escape(name)+r'\][^\n]*\n(.*?)(?=^\[|\Z)'
        match=re.search(pattern,text)
        if not match:return text+'\n['+name+']\n'+''.join(f'{k} = {v}\n' for k,v in values.items())
        body=match[1]
        additions=''.join(f'{k} = {v}\n' for k,v in values.items() if not re.search(r'(?m)^\s*'+re.escape(k)+r'\s*=',body))
        return text[:match.end()]+additions+text[match.end():]
    text=patch_section('DISPLAY',values,text)
    # QtVCP Info is also imported by Gmoccapy; its speed fields use int(text).
    # Normalize existing display values too, preserving their numeric settings.
    def normalize_speeds(match):
        body=re.sub(r'(?m)^(\s*(?:DEFAULT|MIN|MAX)_SPINDLE_(?:\d+_)?SPEED\s*=\s*)([+-]?\d+\.0+)(\s*(?:[#;][^\n]*)?)$',
                    lambda m:m[1]+str(int(float(m[2])))+m[3],match[1])
        return '[DISPLAY]\n'+body
    text=re.sub(r'(?ms)^\[DISPLAY\][^\n]*\n(.*?)(?=^\[|\Z)',normalize_speeds,text)
    text=patch_section('FILTER',dict(PROGRAM_EXTENSION='.ngc,.nc,.tap GCode File (*.ngc, *.nc, *.tap)'),text)
    text=re.sub(r'(?m)^(KINEMATICS\s*=\s*trivkins[^\n]*?)\s+kinstype=BOTH\s*$',r'\1',text)
    return text
