"""Explicit machine fixture: unlike new projects, tests supply a known pulse scale."""
from config_core import defaults as new_project_defaults

def configured_defaults():
    c=new_project_defaults()
    c['mesa_gpio']=[];c['board_profile']='custom';c['discovery']=None;c['remote_enabled']=True
    c['spindle']['invert_pwm']=False # Generic fixture has no discovered physical PWM pin.
    for axis in c['axes']:axis['scale']=400.
    return c
