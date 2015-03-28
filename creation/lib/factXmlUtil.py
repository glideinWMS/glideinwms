import os

def get_submit_dir(conf_dom):
    return os.path.join("%s/glidein_%s" % (conf_dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_dir'),
        conf_dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name')))

def get_stage_dir(conf_dom):
    return os.path.join("%s/glidein_%s" % (conf_dom.getElementsByTagName(u'stage')[0].getAttribute(u'base_dir'),
        conf_dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name')))

def get_monitor_dir(conf_dom):
    return os.path.join("%s/glidein_%s" % (conf_dom.getElementsByTagName(u'monitor')[0].getAttribute(u'base_dir'),
        conf_dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name')))

def get_log_dir(conf_dom):
    return os.path.join("%s/glidein_%s" % (conf_dom.getElementsByTagName(u'submit')[0].getAttribute(u'base_log_dir'),
        conf_dom.getElementsByTagName(u'glidein')[0].getAttribute(u'glidein_name')))
